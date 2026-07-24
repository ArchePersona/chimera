/**
 * inspector.js — Cartridge Inspector logic.
 *
 * Handles data fetching, tab switching, validation, version history,
 * and raw JSON display for forged cartridges.
 */
(function () {
    'use strict';

    var BASE = (function () {
        var el = document.querySelector('[data-cartridge-id]');
        if (!el) return '';
        var a = document.createElement('a');
        a.href = '/chimera/';
        return a.pathname.replace(/\/$/, '');
    })();

    function api(path) {
        return BASE + '/api' + path;
    }

    var cartrigeId = null;
    var cartridgeData = null;

    // ---- Helpers ----

    function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
    function qsa(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

    function show(el) { if (el) el.classList.remove('hidden'); }
    function hide(el) { if (el) el.classList.add('hidden'); }

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

    function renderList(items) {
        if (!items || items.length === 0) return '<span class="empty-value">—</span>';
        return '<ul class="tag-list">' + items.map(function (v) {
            return '<li class="tag">' + escapeHtml(v) + '</li>';
        }).join('') + '</ul>';
    }

    function escapeHtml(s) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(s));
        return d.innerHTML;
    }

    function formatDate(iso) {
        if (!iso) return '—';
        var d = new Date(iso);
        return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }

    // ---- Fetch Cartridge ----

    function fetchCartridge(id) {
        fetch(api('/cartridges/' + id))
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                cartridgeData = data;
                renderCartridge(data);
                show(qs('#inspector-content'));
                hide(qs('#inspector-loading'));
            })
            .catch(function (err) {
                hide(qs('#inspector-loading'));
                var em = qs('#error-message');
                if (em) em.textContent = 'Failed to load cartridge: ' + err.message;
                show(qs('#inspector-error'));
                toast('Failed to load cartridge', 'error');
            });
    }

    // ---- Render Cartridge ----

    function renderCartridge(data) {
        var c = data.cartridge;
        var lc = data.lifecycle;

        qs('#cartridge-name').textContent = c.identity.display_name;
        qs('#cartridge-id').textContent = c.manifest.cartridge_id;
        qs('#cartridge-summary').textContent = c.identity.summary || '';

        // Lifecycle badge
        var badge = qs('#lifecycle-badge');
        badge.textContent = lc.state;
        badge.className = 'lifecycle-badge lifecycle-' + lc.state;

        // Identity
        qs('#identity-display-name').textContent = c.identity.display_name;
        qs('#identity-identifier').textContent = c.identity.identifier;
        qs('#identity-summary').textContent = c.identity.summary || '—';
        qs('#identity-description').textContent = c.identity.description || '—';
        qs('#identity-aliases').innerHTML = renderList(c.identity.aliases);

        // Character
        qs('#character-core-values').innerHTML = renderList(c.character.core_values);
        qs('#character-motivations').innerHTML = renderList(c.character.motivations);
        qs('#character-strengths').innerHTML = renderList(c.character.strengths);
        qs('#character-limitations').innerHTML = renderList(c.character.limitations);
        qs('#character-goals').innerHTML = renderList(c.character.goals);
        qs('#character-boundaries').innerHTML = renderList(c.character.boundaries);

        // Communication
        qs('#communication-style').textContent = c.communication.communication_style || '—';
        qs('#communication-tone').innerHTML = renderList(c.communication.tone);
        qs('#communication-vocabulary').innerHTML = renderList(c.communication.vocabulary_preferences);
        qs('#communication-responses').innerHTML = renderList(c.communication.response_tendencies);
        qs('#communication-formatting').innerHTML = renderList(c.communication.formatting_preferences);

        // Preferences
        var tbody = qs('#preference-table tbody');
        tbody.innerHTML = '';
        if (c.preferences && c.preferences.entries && c.preferences.entries.length > 0) {
            c.preferences.entries.forEach(function (e) {
                var tr = document.createElement('tr');
                tr.innerHTML = '<td class="mono">' + escapeHtml(e.key) + '</td><td>' + escapeHtml(e.value) + '</td>';
                tbody.appendChild(tr);
            });
        } else {
            var tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="2" class="empty-value">No preferences defined</td>';
            tbody.appendChild(tr);
        }

        // Behavior
        var bp = qs('#behavior-policies');
        bp.innerHTML = '';
        if (c.behavior && c.behavior.policies && c.behavior.policies.length > 0) {
            c.behavior.policies.forEach(function (p) {
                var div = document.createElement('div');
                div.className = 'behavior-item';
                div.innerHTML = '<span class="behavior-id mono">' + escapeHtml(p.identifier) + '</span>' +
                    '<span class="behavior-title">' + escapeHtml(p.title) + '</span>';
                bp.appendChild(div);
            });
        } else {
            bp.innerHTML = '<p class="empty-value">No behavior policies defined</p>';
        }

        // Raw JSON
        qs('#raw-json code').textContent = JSON.stringify(c, null, 2);
    }

    // ---- Validation ----

    function fetchValidation(id) {
        show(qs('#validation-loading'));
        hide(qs('#validation-results'));

        fetch(api('/cartridges/' + id + '/validation'))
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                hide(qs('#validation-loading'));
                renderValidation(data);
                show(qs('#validation-results'));
            })
            .catch(function (err) {
                hide(qs('#validation-loading'));
                toast('Validation failed: ' + err.message, 'error');
            });
    }

    function renderValidation(data) {
        var summary = qs('#validation-summary');
        if (data.valid) {
            summary.innerHTML = '<div class="validation-pass">All module validations passed</div>';
        } else {
            summary.innerHTML = '<div class="validation-fail">Module validation failed — ' + data.errors.length + ' error(s)</div>';
        }

        var errList = qs('#validation-errors');
        errList.innerHTML = '';
        if (data.errors.length === 0) {
            hide(qs('#validation-errors-section'));
        } else {
            show(qs('#validation-errors-section'));
            data.errors.forEach(function (e) {
                var li = document.createElement('li');
                li.className = 'validation-item validation-error';
                li.innerHTML = '<strong>' + escapeHtml(e.code) + '</strong> <span class="field-ref">' + escapeHtml(e.field) + '</span> — ' + escapeHtml(e.message);
                errList.appendChild(li);
            });
        }

        var warnList = qs('#validation-warnings');
        warnList.innerHTML = '';
        if (!data.warnings || data.warnings.length === 0) {
            hide(qs('#validation-warnings-section'));
        } else {
            show(qs('#validation-warnings-section'));
            data.warnings.forEach(function (w) {
                var li = document.createElement('li');
                li.className = 'validation-item validation-warn';
                li.innerHTML = '<span class="field-ref">' + escapeHtml(w.field) + '</span> — ' + escapeHtml(w.message);
                warnList.appendChild(li);
            });
        }

        // Specification compliance
        var specDiv = qs('#validation-spec');
        if (data.specification) {
            if (data.specification.compliant) {
                specDiv.innerHTML = '<div class="validation-pass">Cartridge complies with Specification v1.0.0</div>';
            } else {
                var vhtml = '<div class="validation-fail">Specification violations detected:</div><ul class="validation-list">';
                data.specification.violations.forEach(function (v) {
                    vhtml += '<li class="validation-item validation-error"><strong>' + escapeHtml(v.rule) + '</strong> at <span class="field-ref">' + escapeHtml(v.location) + '</span> — ' + escapeHtml(v.reason) + '</li>';
                });
                vhtml += '</ul>';
                specDiv.innerHTML = vhtml;
            }
        }
    }

    // ---- Versions ----

    function fetchVersions(id) {
        show(qs('#versions-loading'));
        hide(qs('#versions-content'));

        fetch(api('/cartridges/' + id + '/versions'))
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                hide(qs('#versions-loading'));
                renderVersions(data);
                show(qs('#versions-content'));
            })
            .catch(function (err) {
                hide(qs('#versions-loading'));
                toast('Failed to load versions: ' + err.message, 'error');
            });
    }

    function renderVersions(data) {
        var summary = qs('#versions-summary');
        summary.textContent = data.total_versions + ' version(s) for identifier "' + data.identifier + '"';

        var list = qs('#version-list');
        list.innerHTML = '';
        if (data.versions.length === 0) {
            list.innerHTML = '<p class="empty-value">No version history available</p>';
            return;
        }

        data.versions.forEach(function (v) {
            var div = document.createElement('div');
            div.className = 'version-item' + (v.is_current ? ' version-current' : '');
            div.innerHTML =
                '<div class="version-header">' +
                    '<span class="version-id mono">' + escapeHtml(v.cartridge_id.substring(0, 8)) + '…</span>' +
                    '<span class="lifecycle-badge lifecycle-' + v.lifecycle_state + '">' + escapeHtml(v.lifecycle_state) + '</span>' +
                    (v.is_current ? '<span class="current-label">Current</span>' : '') +
                '</div>' +
                '<div class="version-meta">' +
                    '<span>v' + escapeHtml(String(v.schema_version)) + '</span>' +
                    '<span>Spec ' + escapeHtml(v.specification_version) + '</span>' +
                    '<span>' + formatDate(v.forged_at) + '</span>' +
                    '<span>' + escapeHtml(v.display_name) + '</span>' +
                '</div>';
            list.appendChild(div);
        });
    }

    // ---- Tabs ----

    function initTabs() {
        var tabs = qsa('.tab-btn');
        var panels = qsa('.tab-panel');

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                var target = tab.getAttribute('data-tab');

                tabs.forEach(function (t) {
                    t.classList.remove('active');
                    t.setAttribute('aria-selected', 'false');
                });
                panels.forEach(function (p) { p.classList.remove('active'); });

                tab.classList.add('active');
                tab.setAttribute('aria-selected', 'true');
                var panel = qs('#panel-' + target);
                if (panel) panel.classList.add('active');

                // Lazy-load validation and versions
                if (target === 'validation' && cartrigeId) fetchValidation(cartrigeId);
                if (target === 'versions' && cartrigeId) fetchVersions(cartrigeId);
            });
        });

        // Keyboard support
        var tabList = qs('[role="tablist"]');
        if (tabList) {
            tabList.addEventListener('keydown', function (e) {
                var idx = tabs.indexOf(document.activeElement);
                if (idx < 0) return;
                if (e.key === 'ArrowRight') {
                    e.preventDefault();
                    var next = tabs[(idx + 1) % tabs.length];
                    next.focus();
                    next.click();
                } else if (e.key === 'ArrowLeft') {
                    e.preventDefault();
                    var prev = tabs[(idx - 1 + tabs.length) % tabs.length];
                    prev.focus();
                    prev.click();
                }
            });
        }
    }

    // ---- Init ----

    function init() {
        var container = qs('.inspector-container');
        if (!container) return;
        cartrigeId = container.getAttribute('data-cartridge-id');
        if (!cartrigeId) {
            show(qs('#inspector-error'));
            hide(qs('#inspector-loading'));
            return;
        }

        initTabs();

        // Copy raw JSON
        var copyBtn = qs('#raw-copy-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', function () {
                var code = qs('#raw-json code');
                if (code && navigator.clipboard) {
                    navigator.clipboard.writeText(code.textContent)
                        .then(function () { toast('JSON copied to clipboard', 'success'); })
                        .catch(function () { toast('Copy failed', 'error'); });
                }
            });
        }

        fetchCartridge(cartrigeId);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
