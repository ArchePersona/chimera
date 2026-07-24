/**
 * CHIMERA Studio — Core Shell & Navigation JavaScript
 */

(function () {
  'use strict';

  // Global Studio Namespace
  window.Studio = window.Studio || {};

  // ---------------------------------------------------------------------------
  // Mobile Navigation Handler
  // ---------------------------------------------------------------------------
  function initMobileNav() {
    const toggleBtn = document.getElementById('mobile-menu-toggle');
    const primaryNav = document.getElementById('primary-nav');

    if (!toggleBtn || !primaryNav) return;

    toggleBtn.addEventListener('click', function () {
      const isExpanded = toggleBtn.getAttribute('aria-expanded') === 'true';
      const newState = !isExpanded;

      toggleBtn.setAttribute('aria-expanded', String(newState));
      primaryNav.classList.toggle('nav-open', newState);

      if (newState) {
        // Focus first link in nav when opened
        const firstLink = primaryNav.querySelector('a');
        if (firstLink) firstLink.focus();
      }
    });

    // Close menu on Escape key press
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && toggleBtn.getAttribute('aria-expanded') === 'true') {
        toggleBtn.setAttribute('aria-expanded', 'false');
        primaryNav.classList.remove('nav-open');
        toggleBtn.focus();
      }
    });

    // Close menu on click outside
    document.addEventListener('click', function (e) {
      if (
        toggleBtn.getAttribute('aria-expanded') === 'true' &&
        !primaryNav.contains(e.target) &&
        !toggleBtn.contains(e.target)
      ) {
        toggleBtn.setAttribute('aria-expanded', 'false');
        primaryNav.classList.remove('nav-open');
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Toast Notifications Helper
  // ---------------------------------------------------------------------------
  Studio.toast = function (message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'alert');

    toast.innerHTML = `
      <span class="toast-message">${escapeHtml(message)}</span>
      <button type="button" class="toast-close" aria-label="Dismiss notification">&times;</button>
    `;

    container.appendChild(toast);

    const closeBtn = toast.querySelector('.toast-close');
    const dismiss = () => {
      toast.classList.add('toast-dismissing');
      setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 300);
    };

    if (closeBtn) {
      closeBtn.addEventListener('click', dismiss);
    }

    if (duration > 0) {
      setTimeout(dismiss, duration);
    }
  };

  // ---------------------------------------------------------------------------
  // Loading Overlay Helper
  // ---------------------------------------------------------------------------
  Studio.showLoading = function (message) {
    const overlay = document.getElementById('global-loading');
    if (!overlay) return;

    const textEl = overlay.querySelector('.loading-text');
    if (textEl && message) {
      textEl.textContent = message;
    }
    overlay.style.display = 'flex';
    overlay.setAttribute('aria-hidden', 'false');
  };

  Studio.hideLoading = function () {
    const overlay = document.getElementById('global-loading');
    if (!overlay) return;

    overlay.style.display = 'none';
    overlay.setAttribute('aria-hidden', 'true');
  };

  // Helper escape HTML
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Initialize on DOM Ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobileNav);
  } else {
    initMobileNav();
  }
})();
