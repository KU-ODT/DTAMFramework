/* operator-log.js - operator-friendly event log panel */
window.ODT = window.ODT || {};

ODT.OperatorLog = (function () {
  const MAX_ENTRIES = 40;
  let bodyEl = null;
  let emptyEl = null;

  function init() {
    bodyEl = document.getElementById('ops-log-body');
    emptyEl = document.getElementById('ops-log-empty');

    const clearBtn = document.getElementById('ops-log-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', clear);
    }
  }

  function clear() {
    if (!bodyEl) return;
    bodyEl.querySelectorAll('.ops-log-entry').forEach((node) => node.remove());
    syncEmptyState();
  }

  function syncEmptyState() {
    if (!emptyEl || !bodyEl) return;
    const hasEntries = !!bodyEl.querySelector('.ops-log-entry');
    emptyEl.style.display = hasEntries ? 'none' : '';
  }

  function timeStamp() {
    const locale = ODT.I18n?.getLanguage() === 'ko' ? 'ko-KR' : 'en-US';
    return new Date().toLocaleTimeString(locale, {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  function normalizeMessage(message, fallback) {
    const text = ODT.humanizeError ? ODT.humanizeError(message, fallback) : String(message || fallback || '');
    return text || fallback || ODT.t('log_no_details');
  }

  function push(level, title, message) {
    if (!bodyEl) return;

    const entry = document.createElement('article');
    entry.className = `ops-log-entry is-${level || 'info'}`;
    entry.innerHTML = `
      <div class="ops-log-icon" aria-hidden="true"></div>
      <div class="ops-log-content">
        <div class="ops-log-row">
          <span class="ops-log-entry-title">${title || ODT.t('log_generic_title')}</span>
          <time class="ops-log-time">${timeStamp()}</time>
        </div>
        <p class="ops-log-message">${normalizeMessage(message, title)}</p>
      </div>
    `;

    bodyEl.appendChild(entry);
    trim();
    syncEmptyState();
    bodyEl.scrollTop = bodyEl.scrollHeight;
  }

  function trim() {
    if (!bodyEl) return;
    const entries = bodyEl.querySelectorAll('.ops-log-entry');
    for (let i = 0; i < entries.length - MAX_ENTRIES; i += 1) {
      entries[i].remove();
    }
  }

  return {
    init,
    clear,
    push,
    info(title, message) {
      push('info', title, message);
    },
    success(title, message) {
      push('success', title, message);
    },
    warn(title, message) {
      push('warn', title, message);
    },
    error(title, message) {
      push('error', title, message);
    },
  };
})();
