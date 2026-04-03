/**
 * ChatCore — shared pharmacy AI assistant logic
 * Used by both chat.html (full page) and base.html (floating widget).
 *
 * Features:
 *  - Text messaging
 *  - RTL auto-detection per message bubble
 *  - Confirmation cards (replaces plain text "Confirm?")
 *  - Ambiguous customer picker cards
 *  - Undo toast (30-second reversible actions)
 *  - Ollama status banner
 *  - Arabic language toggle
 */

const ChatCore = (() => {
  // ─── State ────────────────────────────────────────────────────────────────
  let _cfg = {};          // set by init()
  let sessionId = null;
  let language = 'en';   // 'en' | 'ar'
  let status = {};        // from /chat/api/status
  let undoTimer = null;

  // ─── Public init ─────────────────────────────────────────────────────────
  function init(config) {
    _cfg = Object.assign({
      messagesEl: null,       // scrollable messages container
      inputEl: null,          // textarea
      sendEl: null,           // send button
      langEl: null,           // language toggle button
      statusBannerEl: null,   // banner element for setup instructions
      onUndoComplete: null,   // callback after undo
    }, config);

    sessionId = localStorage.getItem('chatSessionId') || _newId();
    localStorage.setItem('chatSessionId', sessionId);

    language = localStorage.getItem('chatLang') || 'en';
    if (_cfg.langEl) _updateLangButton();

    _checkStatus();

    // Wire send button
    if (_cfg.sendEl) _cfg.sendEl.addEventListener('click', () => _sendFromInput());

    // Wire Enter key (Shift+Enter = newline)
    if (_cfg.inputEl) {
      _cfg.inputEl.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); _sendFromInput(); }
      });
      _cfg.inputEl.addEventListener('input', _autoRtlInput);
    }

    // Wire language toggle
    if (_cfg.langEl) _cfg.langEl.addEventListener('click', toggleLanguage);
  }

  // ─── Session ─────────────────────────────────────────────────────────────
  function _newId() {
    return 'xxxx-xxxx'.replace(/x/g, () => Math.floor(Math.random() * 16).toString(16));
  }

  function getSessionId() { return sessionId; }

  function clearSession() {
    fetch('/chat/api/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });
    sessionId = _newId();
    localStorage.setItem('chatSessionId', sessionId);
    if (_cfg.messagesEl) _cfg.messagesEl.innerHTML = '';
  }

  // ─── Status check ─────────────────────────────────────────────────────────
  async function _checkStatus() {
    try {
      const res = await fetch('/chat/api/status');
      status = await res.json();
      _renderStatusBanner();
    } catch (e) {
      console.warn('Could not fetch chat status:', e);
    }
  }

  function _renderStatusBanner() {
    if (!_cfg.statusBannerEl) return;
    const instructions = status.setup_instructions || {};
    const msgs = [];
    if (!status.ollama_available && instructions.ollama) {
      msgs.push(`🧠 <strong>LLM not running</strong> — rule-based mode only. <code>${instructions.ollama}</code>`);
    }
    if (msgs.length > 0) {
      _cfg.statusBannerEl.innerHTML = msgs.join('<br>');
      _cfg.statusBannerEl.style.display = 'block';
    } else {
      _cfg.statusBannerEl.style.display = 'none';
    }
  }

  // ─── Language toggle ──────────────────────────────────────────────────────
  function toggleLanguage() {
    language = (language === 'en') ? 'ar' : 'en';
    localStorage.setItem('chatLang', language);
    _updateLangButton();
    if (_cfg.inputEl) {
      _cfg.inputEl.dir = language === 'ar' ? 'rtl' : 'ltr';
    }
  }

  function _updateLangButton() {
    if (!_cfg.langEl) return;
    _cfg.langEl.textContent = language === 'en' ? 'AR' : 'EN';
    _cfg.langEl.title = language === 'en' ? 'Switch to Arabic' : 'Switch to English';
  }

  // ─── RTL auto-detection ───────────────────────────────────────────────────
  function _hasArabic(text) {
    return /[\u0600-\u06FF]/.test(text);
  }

  function _autoRtlInput() {
    if (!_cfg.inputEl) return;
    const text = _cfg.inputEl.value;
    _cfg.inputEl.dir = _hasArabic(text) ? 'rtl' : 'ltr';
  }

  function _setMsgDir(el, text) {
    el.dir = _hasArabic(text) ? 'rtl' : 'ltr';
    if (_hasArabic(text)) {
      el.style.fontFamily = "'Segoe UI', 'Tahoma', 'Arial Unicode MS', sans-serif";
      el.style.fontSize = '14px';
    }
  }

  // ─── Message rendering ────────────────────────────────────────────────────
  function renderMessage(text, isUser, opts = {}) {
    if (!_cfg.messagesEl || !text) return null;

    const wrap = document.createElement('div');
    wrap.className = isUser ? 'msg-wrap msg-user' : 'msg-wrap msg-bot';

    const bubble = document.createElement('div');
    bubble.className = isUser ? 'msg-bubble user-bubble' : 'msg-bubble bot-bubble';

    // Parse basic markdown (bold, italic, newlines)
    const html = _mdToHtml(text);
    bubble.innerHTML = html;
    _setMsgDir(bubble, text);

    wrap.appendChild(bubble);

    _cfg.messagesEl.appendChild(wrap);
    _scrollBottom();
    return wrap;
  }

  function _mdToHtml(text) {
    return text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  function renderTypingIndicator() {
    if (!_cfg.messagesEl) return null;
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap msg-bot typing-wrap';
    wrap.innerHTML = '<div class="msg-bubble bot-bubble typing-indicator"><span></span><span></span><span></span></div>';
    _cfg.messagesEl.appendChild(wrap);
    _scrollBottom();
    return wrap;
  }

  function removeTypingIndicator(el) {
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }

  function renderStreamingBubble() {
    if (!_cfg.messagesEl) return null;
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap msg-bot';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble bot-bubble streaming-bubble';

    wrap.appendChild(bubble);
    _cfg.messagesEl.appendChild(wrap);
    _scrollBottom();

    let accumulated = '';
    return {
      el: wrap,
      bubble,
      append(token) {
        accumulated += token;
        bubble.innerHTML = _mdToHtml(accumulated);
        _setMsgDir(bubble, accumulated);
        _scrollBottom();
      },
      finalize() {
        bubble.classList.remove('streaming-bubble');
      },
      getText() { return accumulated; },
    };
  }

  function _scrollBottom() {
    if (_cfg.messagesEl) {
      _cfg.messagesEl.scrollTop = _cfg.messagesEl.scrollHeight;
    }
  }

  /** Yes / No for new-customer flow only (no action_preview card). */
  function renderConfirmCustomer(data) {
    if (!_cfg.messagesEl) return;
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap msg-bot';
    const row = document.createElement('div');
    row.className = 'confirm-yn-row';
    row.innerHTML = '<button type="button" class="btn-yn-yes">Yes</button>'
      + '<button type="button" class="btn-yn-no">No</button>';
    const [yesBtn, noBtn] = row.querySelectorAll('button');
    function done(v) {
      yesBtn.disabled = true;
      noBtn.disabled = true;
      quickSend(v);
    }
    yesBtn.addEventListener('click', () => done('yes'));
    noBtn.addEventListener('click', () => done('no'));
    wrap.appendChild(row);
    _cfg.messagesEl.appendChild(wrap);
    _scrollBottom();
  }

  // ─── Ambiguous customer picker ────────────────────────────────────────────
  function renderAmbiguousCard(candidates) {
    if (!_cfg.messagesEl || !candidates || !candidates.length) return;

    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap msg-bot';

    const card = document.createElement('div');
    card.className = 'picker-card';
    let html = '<div class="picker-list">';
    candidates.slice(0, 8).forEach((c, i) => {
      const debt = c.debt
        ? `<span class="picker-debt">$${Number(c.debt).toLocaleString('en', {minimumFractionDigits: 2})}</span>`
        : '';
      html += `<button class="picker-item" onclick="ChatCore.quickSend(${JSON.stringify(c.name)})">
        <span class="picker-avatar"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span>
        <span class="picker-name">${_esc(c.name)}</span>${debt}
      </button>`;
    });
    html += '</div>';
    card.innerHTML = html;
    wrap.appendChild(card);
    _cfg.messagesEl.appendChild(wrap);
    _scrollBottom();
  }

  // ─── Undo toast ───────────────────────────────────────────────────────────
  function renderUndoToast(message) {
    // Remove any existing toast
    const existing = document.querySelector('.undo-toast');
    if (existing) existing.remove();
    if (undoTimer) clearTimeout(undoTimer);

    const toast = document.createElement('div');
    toast.className = 'undo-toast';
    toast.innerHTML = `
      <span class="toast-msg">${_esc(message)}</span>
      <button class="undo-btn" onclick="ChatCore.doUndo()">↩ Undo</button>
      <button class="toast-close" onclick="this.closest('.undo-toast').remove()" title="Dismiss">✕</button>
    `;

    document.body.appendChild(toast);

    // Auto-dismiss after 5 seconds
    undoTimer = setTimeout(() => {
      toast.classList.add('toast-hiding');
      setTimeout(() => toast.remove(), 350);
    }, 5000);
  }

  async function doUndo() {
    const existing = document.querySelector('.undo-toast');
    if (existing) existing.remove();
    if (undoTimer) clearTimeout(undoTimer);

    try {
      const res = await fetch('/chat/api/undo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
      const data = await res.json();
      renderMessage(data.response || 'Action undone.', false);
      _emitLedgerUpdated(data);
      if (_cfg.onUndoComplete) _cfg.onUndoComplete();
    } catch (e) {
      renderMessage('Could not undo. Please check the transaction manually.', false);
    }
  }

  // ─── Send message ─────────────────────────────────────────────────────────
  function _sendFromInput() {
    if (!_cfg.inputEl) return;
    const text = _cfg.inputEl.value.trim();
    if (!text) return;
    _cfg.inputEl.value = '';
    _cfg.inputEl.dir = 'ltr';
    sendMessage(text);
  }

  function quickSend(text) {
    sendMessage(text);
  }

  async function sendMessage(text) {
    if (!text || !text.trim()) return;

    renderMessage(text, true);

    const typing = renderTypingIndicator();
    const payload = JSON.stringify({
      message: text,
      session_id: sessionId,
      language: language,
    });

    try {
      const res = await fetch('/chat/api/message/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
      });

      if (!res.ok || !res.headers.get('content-type')?.includes('text/event-stream')) {
        throw new Error('SSE not available');
      }

      removeTypingIndicator(typing);
      await _handleSSEStream(res);

    } catch (_sseErr) {
      // Fallback to non-streaming endpoint
      try {
        const res = await fetch('/chat/api/message', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
        });

        const data = await res.json();
        removeTypingIndicator(typing);
        _handleNonStreamingResponse(data);
      } catch (_fallbackErr) {
        removeTypingIndicator(typing);
        renderMessage('Connection error. Please try again.', false);
      }
    }
  }

  function _emitLedgerUpdated(src) {
    if (!src || !src.ledger_changed) return;
    window.dispatchEvent(new CustomEvent('pharmacy:ledger-updated', {
      detail: {
        ledger_changed: true,
        updated_customer_id: src.updated_customer_id,
        updated_customer_name: src.updated_customer_name,
        updated_balance: src.updated_balance,
        success: src.success,
        intent: src.intent,
      },
    }));
  }

  async function _handleSSEStream(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let meta = null;
    let streamBubble = null;
    let doneLedger = null;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            var currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);

            if (currentEvent === 'meta') {
              try { meta = JSON.parse(dataStr); } catch (_) {}

            } else if (currentEvent === 'token') {
              let piece = dataStr;
              try {
                const obj = JSON.parse(dataStr);
                if (obj && typeof obj.text === 'string') piece = obj.text;
              } catch (_) {}
              if (!streamBubble) streamBubble = renderStreamingBubble();
              streamBubble.append(piece);

            } else if (currentEvent === 'done') {
              if (streamBubble) streamBubble.finalize();
              try {
                const obj = JSON.parse(dataStr);
                if (obj && obj.ledger_changed) doneLedger = obj;
              } catch (_) {}
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    if (!streamBubble && meta?.response) {
      renderMessage(meta.response, false);
    }

    if (meta) {
      if (meta.needs === 'clarification' && meta.candidates?.length) {
        renderAmbiguousCard(meta.candidates);
      } else if (meta.needs === 'confirm_customer') {
        renderConfirmCustomer(meta);
      }
      if (meta.undo_available && meta.success && (streamBubble?.getText() || meta.response)) {
        const toastText = (streamBubble?.getText() || meta.response).replace(/\*\*/g, '').substring(0, 80);
        renderUndoToast(toastText);
      }
    }

    _emitLedgerUpdated(meta && meta.ledger_changed ? meta : doneLedger);
  }

  function _handleNonStreamingResponse(data) {
    if (data.response) {
      renderMessage(data.response, false);
    }

    if (data.needs === 'clarification' && data.candidates && data.candidates.length) {
      renderAmbiguousCard(data.candidates);
    } else if (data.needs === 'confirm_customer') {
      renderConfirmCustomer(data);
    }

    if (data.undo_available && data.success && data.response) {
      renderUndoToast(data.response.replace(/\*\*/g, '').substring(0, 80));
    }
    _emitLedgerUpdated(data);
  }

  // ─── Load history ─────────────────────────────────────────────────────────
  async function loadHistory() {
    if (!sessionId || !_cfg.messagesEl) return;
    try {
      const res = await fetch(`/chat/api/history?session_id=${sessionId}`);
      const data = await res.json();
      const messages = data.messages || [];
      if (messages.length === 0) {
        _showWelcome();
        return;
      }
      _cfg.messagesEl.innerHTML = '';
      messages.forEach(m => {
        renderMessage(m.message, m.role === 'user');
      });
    } catch (_) {
      _showWelcome();
    }
  }

  function _showWelcome() {
    renderMessage(
      'مرحبا! / Hello! I\'m your pharmacy assistant.\n\n' +
      'Try: **"Ahmad owes 50"**, **"Ahmad dafa3 100"**, **"كم عند احمد"**\n\n' +
      'Type **help** for all commands.',
      false
    );
  }

  // ─── Utils ────────────────────────────────────────────────────────────────
  function _esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ─── Public API ───────────────────────────────────────────────────────────
  return {
    init,
    sendMessage,
    quickSend,
    toggleLanguage,
    loadHistory,
    clearSession,
    getSessionId,
    renderMessage,
    renderStreamingBubble,
    renderAmbiguousCard,
    renderUndoToast,
    doUndo,
    get language() { return language; },
    get status() { return status; },
  };
})();
