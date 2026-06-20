// Thread polling, optimistic send, long-press action menu, swipe-to-reveal time
(function () {
  if (typeof THREAD_ID === 'undefined') return;

  const chatWindow = document.getElementById('chat-window');
  let lastId = 0;

  // Find the highest message id already rendered on page load
  document.querySelectorAll('.message[data-id]').forEach(function (el) {
    const id = parseInt(el.getAttribute('data-id'), 10);
    if (id > lastId) lastId = id;
  });

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function scrollToBottom() {
    if (chatWindow) chatWindow.scrollTop = chatWindow.scrollHeight;
  }
  scrollToBottom();

  const REACT_EMOJI = { laugh: '😂', cook: '👨‍🍳', fraud: '🚨', receipt: '🧾' };

  // Quoted-parent element shown at the top of a reply bubble. `reply` is
  // { author, body } (from messages.json) or the active reply context.
  function replyQuoteEl(reply) {
    const q = document.createElement('div');
    q.className = 'reply-quote';
    const a = document.createElement('span');
    a.className = 'reply-quote-author';
    a.textContent = reply.author;
    const t = document.createElement('span');
    t.className = 'reply-quote-text';
    t.textContent = reply.body;
    q.appendChild(a); q.appendChild(t);
    return q;
  }

  // ── Reaction badges (compact, under the bubble) ───────────────────────────
  function renderReactions(msgEl, counts) {
    const col = msgEl.querySelector('.message-col');
    if (!col) return;
    let wrap = col.querySelector('.msg-reactions');
    let html = '';
    ['laugh', 'cook', 'fraud', 'receipt'].forEach(function (t) {
      if (counts && counts[t]) {
        html += '<span class="msg-react-badge" data-reaction="' + t + '">' +
                REACT_EMOJI[t] + ' ' + counts[t] + '</span>';
      }
    });
    if (!html) { if (wrap) wrap.remove(); return; }
    if (!wrap) { wrap = document.createElement('div'); wrap.className = 'msg-reactions'; col.appendChild(wrap); }
    wrap.innerHTML = html;
  }

  // ── Message element builder (used by polling) ─────────────────────────────
  function buildMessageEl(msg) {
    const wrapper = document.createElement('div');
    const isMine = msg.is_mine;
    wrapper.className = 'message message-' + msg.type +
      (msg.type !== 'system' ? (' ' + (isMine ? 'message-mine' : 'message-theirs')) : '');
    wrapper.setAttribute('data-id', msg.id);
    wrapper.id = 'msg-' + msg.id;

    if (msg.type === 'system') {
      const body = document.createElement('div');
      body.className = 'message-system-body';
      body.textContent = msg.body;
      wrapper.appendChild(body);
      return wrapper;
    }

    wrapper.setAttribute('data-mine', isMine ? '1' : '0');
    wrapper.setAttribute('data-can-delete', msg.can_delete ? '1' : '0');
    wrapper.setAttribute('data-author-id', msg.author_id || '');
    wrapper.setAttribute('data-author-name', msg.author || 'this user');
    wrapper.setAttribute('data-my-reactions', (msg.user_reactions || []).join(','));

    const col = document.createElement('div');
    col.className = 'message-col';
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    if (msg.reply_to) bubble.appendChild(replyQuoteEl(msg.reply_to));
    if (!isMine) {
      const author = document.createElement('div');
      author.className = 'message-author';
      author.textContent = msg.author;
      bubble.appendChild(author);
    }
    const text = document.createElement('div');
    text.className = 'message-text';
    text.textContent = msg.body;
    bubble.appendChild(text);
    col.appendChild(bubble);
    wrapper.appendChild(col);

    if (msg.reactions && Object.keys(msg.reactions).length) {
      renderReactions(wrapper, msg.reactions);
    }

    const time = document.createElement('span');
    time.className = 'swipe-time';
    if (msg.created_at) {
      const d = new Date(msg.created_at);
      time.textContent = pad(d.getHours()) + ':' + pad(d.getMinutes());
    }
    col.appendChild(time);
    return wrapper;
  }

  // ── Polling — 3s interval, paused when tab is hidden ─────────────────────
  function pollMessages() {
    if (!chatWindow) return;
    fetch('/api/threads/' + THREAD_ID + '/messages.json?after=' + lastId)
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        if (!data.length) return;
        const wasAtBottom = chatWindow.scrollHeight - chatWindow.scrollTop <= chatWindow.clientHeight + 60;
        data.forEach(function (msg) {
          // Drop the optimistic placeholder for our own confirmed message
          if (msg.is_mine) {
            const optEl = document.querySelector('.message-pending[data-opt-body]');
            if (optEl && optEl.getAttribute('data-opt-body') === msg.body) {
              optEl.remove();
            }
          }
          const existing = document.getElementById('msg-' + msg.id);
          if (!existing) {
            chatWindow.appendChild(buildMessageEl(msg));
          }
          if (msg.id > lastId) lastId = msg.id;
        });
        if (wasAtBottom) scrollToBottom();
      })
      .catch(function () {});
  }

  let _pollTimer = null;
  function startPoll() {
    if (_pollTimer) clearInterval(_pollTimer);
    _pollTimer = setInterval(pollMessages, 3000);
    window._threadPollTimer = _pollTimer; // exposed for Turbo cleanup
  }
  function pausePoll() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
    window._threadPollTimer = null;
  }
  startPoll();
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) { pausePoll(); } else { pollMessages(); startPoll(); }
  });

  // ── Message actions (shared) ──────────────────────────────────────────────
  function deleteMessage(messageId) {
    fetch('/api/messages/' + messageId + '/delete', { method: 'POST' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        if (data.success) {
          const el = document.getElementById('msg-' + messageId);
          if (el) el.remove();
        }
      })
      .catch(function () {
        if (typeof showToast === 'function') showToast('Delete failed', 'error');
      });
  }

  function toggleReaction(msgEl, rtype) {
    const id = msgEl.getAttribute('data-id');
    if (!id || id.indexOf('opt-') === 0) return; // can't react to an unsent message
    fetch('/api/messages/' + id + '/react', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reaction_type: rtype }),
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        // Keep the per-user reaction set in sync for the next menu open
        const mine = (msgEl.getAttribute('data-my-reactions') || '').split(',').filter(Boolean);
        const i = mine.indexOf(rtype);
        if (data.added && i < 0) mine.push(rtype);
        if (!data.added && i >= 0) mine.splice(i, 1);
        msgEl.setAttribute('data-my-reactions', mine.join(','));
        renderReactions(msgEl, data.counts);
      })
      .catch(function () {
        if (typeof showToast === 'function') showToast('Could not react', 'error');
      });
  }

  function copyText(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text)
        .then(function () { if (typeof showToast === 'function') showToast('Copied', 'success'); })
        .catch(function () { if (typeof showToast === 'function') showToast('Copy failed', 'error'); });
    }
  }

  // ── Long-press action menu ────────────────────────────────────────────────
  const menuOverlay = document.getElementById('msg-actions');
  const menuCtx = { el: null, id: null, text: '', mine: false, canDelete: false, authorId: null, authorName: null };

  function openMenu(msgEl) {
    if (!menuOverlay || !msgEl) return;
    menuCtx.el = msgEl;
    menuCtx.id = msgEl.getAttribute('data-id');
    const textEl = msgEl.querySelector('.message-text');
    menuCtx.text = textEl ? textEl.textContent : '';
    menuCtx.mine = msgEl.getAttribute('data-mine') === '1';
    menuCtx.canDelete = msgEl.getAttribute('data-can-delete') === '1';
    menuCtx.authorId = msgEl.getAttribute('data-author-id') || null;
    menuCtx.authorName = msgEl.getAttribute('data-author-name') || 'this user';

    const delBtn = menuOverlay.querySelector('[data-action="delete"]');
    const repBtn = menuOverlay.querySelector('[data-action="report"]');
    if (delBtn) delBtn.hidden = !menuCtx.canDelete;
    if (repBtn) repBtn.hidden = menuCtx.mine || !menuCtx.authorId;

    // Reflect which reactions this user already has
    const mine = (msgEl.getAttribute('data-my-reactions') || '').split(',').filter(Boolean);
    menuOverlay.querySelectorAll('.msg-react').forEach(function (b) {
      b.classList.toggle('reacted', mine.indexOf(b.getAttribute('data-reaction')) >= 0);
    });
    menuOverlay.hidden = false;
  }
  function closeMenu() { if (menuOverlay) menuOverlay.hidden = true; }

  if (menuOverlay) {
    menuOverlay.addEventListener('click', function (e) {
      if (e.target === menuOverlay) { closeMenu(); return; } // tap backdrop
      const react = e.target.closest('.msg-react');
      if (react) {
        if (menuCtx.el) toggleReaction(menuCtx.el, react.getAttribute('data-reaction'));
        closeMenu();
        return;
      }
      const act = e.target.closest('.msg-action');
      if (!act) return;
      const action = act.getAttribute('data-action');
      if (action === 'cancel') { closeMenu(); return; }
      if (action === 'reply')  { startReply(menuCtx); closeMenu(); return; }
      if (action === 'copy')   { copyText(menuCtx.text); closeMenu(); return; }
      if (action === 'delete') {
        closeMenu();
        if (confirm('Delete this message?')) deleteMessage(menuCtx.id);
        return;
      }
      if (action === 'report') {
        closeMenu();
        openReportFor(menuCtx.id, menuCtx.authorId, menuCtx.authorName);
        return;
      }
    });
  }

  // ── Long-press opens the action menu (no swipe gesture) ───────────────────
  if (chatWindow) {
    const LONG_MS = 450, MOVE_CANCEL = 10;
    let startX = 0, startY = 0, pressTimer = null, pressEl = null;

    // The finger-lift after a long-press synthesizes a click that would land on
    // the just-opened sheet (often the backdrop) and instantly dismiss it.
    // Swallow exactly that one click; a stray timer reset avoids eating a real tap.
    let swallowClick = false, swallowTimer = null;
    function armClickSwallow() {
      swallowClick = true;
      if (swallowTimer) clearTimeout(swallowTimer);
      swallowTimer = setTimeout(function () { swallowClick = false; }, 700);
    }
    document.addEventListener('click', function (e) {
      if (!swallowClick) return;
      swallowClick = false;
      if (swallowTimer) { clearTimeout(swallowTimer); swallowTimer = null; }
      e.stopPropagation();
      e.preventDefault();
    }, true);

    function clearPress() {
      if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; }
      if (pressEl) { pressEl.classList.remove('pressing'); }
      pressEl = null;
    }

    chatWindow.addEventListener('touchstart', function (e) {
      if (e.touches.length !== 1) return;
      const t = e.touches[0];
      startX = t.clientX; startY = t.clientY;
      const msgEl = e.target.closest('.message[data-id]');
      // long-press only on real user messages (system msgs have no data-mine)
      const target = (msgEl && msgEl.getAttribute('data-mine') !== null && menuOverlay) ? msgEl : null;
      if (target) {
        pressEl = target;
        pressEl.classList.add('pressing');
        pressTimer = setTimeout(function () {
          pressTimer = null;
          const el = pressEl;
          if (el) el.classList.remove('pressing');
          pressEl = null;
          if (typeof FSNative !== 'undefined' && FSNative.haptic) FSNative.haptic('MEDIUM');
          openMenu(el);
          armClickSwallow();
        }, LONG_MS);
      }
    }, { passive: true });

    // Any real finger movement = a scroll, so cancel the pending long-press and
    // let native vertical scrolling proceed untouched (passive, no preventDefault).
    chatWindow.addEventListener('touchmove', function (e) {
      if (!pressTimer) return;
      const t = e.touches[0];
      if (Math.abs(t.clientX - startX) > MOVE_CANCEL || Math.abs(t.clientY - startY) > MOVE_CANCEL) {
        clearPress();
      }
    }, { passive: true });

    chatWindow.addEventListener('touchend', clearPress);
    chatWindow.addEventListener('touchcancel', clearPress);

    // Desktop / fallback — right-click opens the same menu
    chatWindow.addEventListener('contextmenu', function (e) {
      const msgEl = e.target.closest('.message[data-id]');
      if (!msgEl || msgEl.getAttribute('data-mine') === null) return;
      e.preventDefault();
      if (menuOverlay && menuOverlay.hidden) openMenu(msgEl);
    });
  }

  // ── Optimistic message send ───────────────────────────────────────────────
  const chatForm     = document.getElementById('chat-form');
  const chatTextarea = document.getElementById('chat-input');
  const chatSendBtn  = document.getElementById('chat-send');
  let _pendingSeq = 0;

  // ── Reply state (set from the long-press "Reply" action) ──
  const replyBar       = document.getElementById('reply-bar');
  const replyBarAuthor = document.getElementById('reply-bar-author');
  const replyBarText   = document.getElementById('reply-bar-text');
  const replyBarCancel = document.getElementById('reply-bar-cancel');
  let replyState = null; // { id, author, body }

  function startReply(ctx) {
    replyState = { id: ctx.id, author: ctx.mine ? 'You' : (ctx.authorName || 'them'), body: ctx.text || '' };
    if (replyBarAuthor) replyBarAuthor.textContent = 'Replying to ' + replyState.author;
    if (replyBarText)   replyBarText.textContent = replyState.body;
    if (replyBar) replyBar.hidden = false;
    if (chatTextarea) chatTextarea.focus();
  }
  function cancelReply() {
    replyState = null;
    if (replyBar) replyBar.hidden = true;
  }
  if (replyBarCancel) replyBarCancel.addEventListener('click', cancelReply);

  function buildOptimisticEl(body, tempId, reply) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message message-user message-mine message-pending';
    wrapper.id = tempId;
    wrapper.setAttribute('data-opt-body', body);
    wrapper.setAttribute('data-mine', '1');

    const col = document.createElement('div');
    col.className = 'message-col';
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    if (reply) bubble.appendChild(replyQuoteEl(reply));
    const text = document.createElement('div');
    text.className = 'message-text';
    text.textContent = body;
    bubble.appendChild(text);
    const dot = document.createElement('span');
    dot.className = 'message-sending-dot';
    dot.setAttribute('aria-hidden', 'true');
    bubble.appendChild(dot);
    col.appendChild(bubble);
    wrapper.appendChild(col);

    const time = document.createElement('span');
    time.className = 'swipe-time';
    const now = new Date();
    time.textContent = pad(now.getHours()) + ':' + pad(now.getMinutes());
    col.appendChild(time);
    return wrapper;
  }

  if (chatForm && chatTextarea) {
    chatForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const body = chatTextarea.value.trim();
      if (!body || !chatWindow) return;

      const activeReply = replyState; // capture before the bar is cleared
      const tempId = 'opt-' + (++_pendingSeq);
      const optEl  = buildOptimisticEl(body, tempId, activeReply);
      chatWindow.appendChild(optEl);
      scrollToBottom();

      chatTextarea.value = '';
      chatTextarea.style.height = '';
      cancelReply();
      if (chatSendBtn) { chatSendBtn.disabled = true; chatSendBtn.classList.add('sending'); }

      const fd = new FormData();
      fd.append('body', body);
      if (activeReply) fd.append('reply_to', activeReply.id);

      fetch(chatForm.action, {
        method: 'POST',
        headers: { 'X-Fetch': '1' },
        body: fd,
      })
        .then(function (r) {
          return r.json().then(function (j) {
            if (!r.ok) {
              var e = new Error(r.status);
              e.serverMessage = j && j.message;
              throw e;
            }
            return j;
          });
        })
        .then(function (data) {
          const confirmed = document.getElementById('msg-' + data.id);
          const el = document.getElementById(tempId);
          if (confirmed) {
            if (el) el.remove();
          } else if (el) {
            // Promote the optimistic element to a real, actionable message
            el.setAttribute('data-id', data.id);
            el.id = 'msg-' + data.id;
            el.removeAttribute('data-opt-body');
            el.classList.remove('message-pending');
            el.setAttribute('data-can-delete', '1');
            el.setAttribute('data-author-name', 'You');
            el.setAttribute('data-my-reactions', '');
            const dot = el.querySelector('.message-sending-dot');
            if (dot) dot.remove();
            if (data.id > lastId) lastId = data.id;
          }
        })
        .catch(function (err) {
          const el = document.getElementById(tempId);
          if (el) el.remove();
          chatTextarea.value = body;
          if (chatSendBtn) chatSendBtn.disabled = false;
          chatTextarea.focus();
          if (err && err.serverMessage && typeof showToast === 'function') {
            showToast(err.serverMessage, 'error');
          }
        })
        .finally(function () {
          if (chatSendBtn) chatSendBtn.classList.remove('sending');
        });

      const emptyState = document.getElementById('chat-empty-state');
      if (emptyState) emptyState.remove();
    });
  }

  // ── Quick prompts (empty thread) — prefill the input ──────────────────────
  if (chatWindow) {
    chatWindow.addEventListener('click', function (e) {
      const chip = e.target.closest('.prompt-chip');
      if (!chip || !chatTextarea) return;
      chatTextarea.value = chip.getAttribute('data-prompt') || '';
      chatTextarea.focus();
      chatTextarea.setSelectionRange(chatTextarea.value.length, chatTextarea.value.length);
      chatTextarea.dispatchEvent(new Event('input'));
    });
  }

  // ── Report a message + block its author (sheet opened from the action menu) ─
  const reportSheet  = document.getElementById('report-sheet');
  let   reportTarget = { messageId: null, authorId: null, authorName: null };

  function openReportFor(messageId, authorId, authorName) {
    if (!reportSheet) return;
    reportTarget = { messageId: messageId, authorId: authorId || null, authorName: authorName || 'this user' };
    const blockBtn = document.getElementById('report-block-btn');
    if (blockBtn) {
      blockBtn.textContent = 'Block ' + reportTarget.authorName;
      blockBtn.style.display = reportTarget.authorId ? '' : 'none';
    }
    reportSheet.hidden = false;
  }
  function closeReportSheet() { if (reportSheet) reportSheet.hidden = true; }

  if (reportSheet) {
    reportSheet.querySelectorAll('.report-option').forEach(function (opt) {
      opt.addEventListener('click', function () {
        const category = opt.getAttribute('data-category');
        const id = reportTarget.messageId;
        closeReportSheet();
        if (!id) return;
        fetch('/api/messages/' + id + '/report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ category: category }),
        })
          .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, status: r.status, body: j }; }); })
          .then(function (res) {
            if (res.ok) {
              if (typeof showToast === 'function') showToast('Report sent. Thanks — our team will review it.', 'success');
            } else if (res.status === 409) {
              if (typeof showToast === 'function') showToast("You've already reported this message.", 'info');
            } else {
              if (typeof showToast === 'function') showToast((res.body && res.body.error) || 'Could not send report.', 'error');
            }
          })
          .catch(function () {
            if (typeof showToast === 'function') showToast('Could not send report.', 'error');
          });
      });
    });

    const blockBtn = document.getElementById('report-block-btn');
    if (blockBtn) {
      blockBtn.addEventListener('click', function () {
        if (!reportTarget.authorId) return;
        if (!confirm('Block ' + reportTarget.authorName + "? You won't see each other's messages anymore.")) return;
        const form = document.getElementById('report-block-form');
        if (form) {
          form.action = '/friends/block/' + reportTarget.authorId;
          form.submit();
        }
      });
    }

    const cancelBtn = document.getElementById('report-cancel-btn');
    if (cancelBtn) cancelBtn.addEventListener('click', closeReportSheet);
    reportSheet.addEventListener('click', function (e) {
      if (e.target === reportSheet) closeReportSheet();
    });
  }
})();
