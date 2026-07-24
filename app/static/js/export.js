/**
 * export.js — Export Experience logic.
 *
 * Fetches export data from the API, renders metadata, JSON preview,
 * and handles copy/download. Never serializes cartridges itself.
 */
(function () {
    'use strict';

    var BASE = (function () {
        var a = document.createElement('a');
        a.href = '/chimera/';
        return a.pathname.replace(/\/$/, '');
    })();

    function api(path) { return BASE + '/api' + path; }

    var cartridgeId = null;
    var exportData = null;
    var serializedJson = '';

    // ---- Helpers ----

    function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
    function show(el) { if (el) el.classList.remove('hidden'); }
    function hide(el) { if (el) el.classList.add('hidden'); }

    function escapeHtml(s) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(String(s)));
        return d.innerHTML;
    }

    function toast(msg, type) {
        var c = qs('#toast-container');
        if (!c) return;
        var t = document.createElement('div');
        t.className = 'toast toast-' + (type || 'info');
        t.textContent = msg;
        c.appendChild(t);
        setTimeout(function () { t.classList.add('toast-fade'); }, 3200);
        setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 3800);
    }

    function announce(msg) {
        var el = qs('#sr-announcer');
        if (el) el.textContent = msg;
    }

    function formatDate(iso) {
        if (!iso) return '—';
        var d = new Date(iso);
        return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(2) + ' MB';
    }

    function truncateChecksum(val) {
        if (!val) return '—';
        return val.substring(0, 16) + '…';
    }

    // ---- Fetch Export Data ----

    function fetchExport(id) {
        fetch(api('/cartridges/' + id + '/export'))
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                exportData = data;
                serializedJson = JSON.stringify(data.cartridge, null, 2);
                renderExport(data);
                show(qs('#export-content'));
                hide(qs('#export-loading'));

                var inspLink = qs('.export-inspector-link');
                if (inspLink) {
                    var href = inspLink.getAttribute('href').replace('{CARTRIDGE_ID}', id);
                    inspLink.setAttribute('href', href);
                }
            })
            .catch(function (err) {
                hide(qs('#export-loading'));
                var em = qs('#error-message');
                if (em) em.textContent = 'Failed to load export: ' + err.message;
                show(qs('#export-error'));
                toast('Failed to load export', 'error');
            });
    }

    // ---- Render ----

    function renderExport(data) {
        var c = data.cartridge;
        var spec = data.specification || {};
        var compat = data.compatibility || {};
        var val = data.validation || {};

        qs('#export-cartridge-id').textContent = c.manifest.cartridge_id;
        qs('#meta-name').textContent = c.identity.display_name;
        qs('#meta-identifier').textContent = c.identity.identifier;
        qs('#meta-uuid').textContent = c.manifest.cartridge_id;
        qs('#meta-version').textContent = 'Schema ' + c.manifest.schema_version;
        qs('#meta-spec').textContent = 'Persona Cartridge v' + c.manifest.specification_version;
        qs('#meta-forged').textContent = formatDate(c.manifest.created_at);

        qs('#meta-size').textContent = formatSize(data.size_bytes);
        qs('#meta-checksum').textContent = truncateChecksum(data.checksum.value);
        qs('#meta-export-count').textContent = data.lifecycle.export_count;

        // Validation status
        var valEl = qs('#export-validation-status');
        if (val.valid) {
            var warnText = val.warning_count > 0
                ? 'Valid with ' + val.warning_count + ' warning(s)'
                : 'Valid';
            valEl.innerHTML = '<div class="validation-pass">' + escapeHtml(warnText) + '</div>';
        } else {
            valEl.innerHTML = '<div class="validation-fail">Invalid — ' + val.errors.length + ' error(s)</div>';
        }

        // Specification
        qs('#compat-spec').textContent = 'Persona Cartridge v' + (spec.specification_version || '1.0.0');

        // JSON preview
        qs('#json-code').textContent = serializedJson;
    }

    // ---- Download ----

    function downloadJson() {
        if (!serializedJson || !exportData) return;
        var blob = new Blob([serializedJson], { type: 'application/json' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = exportData.filename || 'cartridge.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        toast('Download started', 'success');
        announce('JSON file download started');
    }

    // ---- Copy ----

    function copyJson() {
        if (!serializedJson) return;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(serializedJson)
                .then(function () {
                    toast('JSON copied to clipboard', 'success');
                    announce('JSON copied to clipboard');
                })
                .catch(function () {
                    fallbackCopy();
                });
        } else {
            fallbackCopy();
        }
    }

    function fallbackCopy() {
        var ta = document.createElement('textarea');
        ta.value = serializedJson;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            toast('JSON copied to clipboard', 'success');
            announce('JSON copied to clipboard');
        } catch (e) {
            toast('Copy failed', 'error');
        }
        document.body.removeChild(ta);
    }

    // ---- Init ----

    function init() {
        var container = qs('.export-container');
        if (!container) return;
        cartridgeId = container.getAttribute('data-cartridge-id');
        if (!cartridgeId) {
            show(qs('#export-error'));
            hide(qs('#export-loading'));
            return;
        }

        qs('#btn-download').addEventListener('click', downloadJson);
        qs('#btn-copy').addEventListener('click', copyJson);
        qs('#btn-copy-preview').addEventListener('click', copyJson);

        fetchExport(cartridgeId);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
