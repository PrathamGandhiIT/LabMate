/**
 * AI LabMate — Core JavaScript
 *
 * Provides:
 * - AI status polling (Gemini API)
 * - Toast notifications
 * - Sidebar mobile toggle
 * - Copy-to-clipboard
 * - Utility helpers
 *
 * No frameworks — plain vanilla JS.
 */

'use strict';

// =====================================================================
// Toast Notification System
// =====================================================================

const Toast = {
  container: null,

  init() {
    this.container = document.getElementById('toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
  },

  show(message, type = 'info', duration = 4000) {
    if (!this.container) this.init();

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;

    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ',
    };

    toast.innerHTML = '';
    const iconSpan = document.createElement('span');
    iconSpan.textContent = icons[type] || icons.info;
    const msgSpan = document.createElement('span');
    msgSpan.textContent = message;
    toast.appendChild(iconSpan);
    toast.appendChild(msgSpan);

    this.container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 300ms ease';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },

  success(msg) { this.show(msg, 'success'); },
  error(msg) { this.show(msg, 'error', 6000); },
  warning(msg) { this.show(msg, 'warning', 5000); },
};


// =====================================================================
// AI Status Checker (Gemini API)
// =====================================================================

const AIStatus = {
  dot: null,
  label: null,
  modelLabel: null,
  retryBtn: null,

  init() {
    this.dot = document.getElementById('ai-status-dot');
    this.label = document.getElementById('ai-status-label');
    this.modelLabel = document.getElementById('ai-model-label');
    this.retryBtn = document.getElementById('ai-retry-btn');

    if (this.retryBtn) {
      this.retryBtn.addEventListener('click', () => this.check());
    }

    // Auto-check on page load
    this.check();
  },

  async check() {
    if (!this.dot || !this.label) return;

    // Set checking state
    this.dot.className = 'status-dot checking';
    this.label.textContent = 'Checking AI connection...';
    if (this.retryBtn) this.retryBtn.disabled = true;

    try {
      const resp = await fetch('/api/health');
      const data = await resp.json();

      if (data.model_available) {
        this.dot.className = 'status-dot connected';
        this.label.textContent = 'AI Connected';
        if (this.modelLabel) {
          this.modelLabel.textContent = data.model_name;
        }
      } else if (data.api_reachable && !data.model_available) {
        this.dot.className = 'status-dot warning';
        this.label.textContent = 'Model unavailable';
        Toast.warning(data.error || 'Model not available');
      } else {
        this.dot.className = 'status-dot error';
        this.label.textContent = 'AI Disconnected';
        Toast.error(data.error || 'Cannot reach Gemini API');
      }

      // Also update sidebar status if present
      this.updateSidebarStatus(data);

    } catch (err) {
      this.dot.className = 'status-dot error';
      this.label.textContent = 'Connection error';
    } finally {
      if (this.retryBtn) this.retryBtn.disabled = false;
    }
  },

  updateSidebarStatus(data) {
    const sidebarDot = document.getElementById('sidebar-status-dot');
    const sidebarLabel = document.getElementById('sidebar-status-label');
    if (!sidebarDot) return;

    if (data.model_available) {
      sidebarDot.className = 'status-dot connected';
      if (sidebarLabel) sidebarLabel.textContent = `${data.model_name} ready`;
    } else if (data.api_reachable) {
      sidebarDot.className = 'status-dot warning';
      if (sidebarLabel) sidebarLabel.textContent = 'Model unavailable';
    } else {
      sidebarDot.className = 'status-dot error';
      if (sidebarLabel) sidebarLabel.textContent = 'AI offline';
    }
  }
};


// =====================================================================
// Sidebar (Mobile Toggle)
// =====================================================================

const Sidebar = {
  init() {
    const toggle = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (!toggle || !sidebar) return;

    toggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('active');
    });

    if (overlay) {
      overlay.addEventListener('click', () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
      });
    }

    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('active');
      }
    });
  }
};


// =====================================================================
// Clipboard
// =====================================================================

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    Toast.success('Copied to clipboard');
  } catch {
    // Fallback for older browsers or non-HTTPS
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      Toast.success('Copied to clipboard');
    } catch {
      Toast.error('Failed to copy — please copy manually');
    }
    document.body.removeChild(textarea);
  }
}


// =====================================================================
// Loading state helpers
// =====================================================================

function setLoading(button, isLoading, originalText) {
  if (isLoading) {
    button.disabled = true;
    button.dataset.originalText = button.textContent;
    button.innerHTML = '';
    const spinner = document.createElement('span');
    spinner.className = 'spinner';
    button.appendChild(spinner);
    const text = document.createTextNode(' Generating...');
    button.appendChild(text);
  } else {
    button.disabled = false;
    button.textContent = originalText || button.dataset.originalText || 'Submit';
  }
}


// =====================================================================
// Safe text setting (never use innerHTML with untrusted content)
// =====================================================================

function safeSetText(element, text) {
  if (element) {
    element.textContent = text;
  }
}


// =====================================================================
// Initialize on DOM ready
// =====================================================================

document.addEventListener('DOMContentLoaded', () => {
  Toast.init();
  Sidebar.init();
  AIStatus.init();
});
