// Thread polling, optimistic message send, and reaction handling
(function () {
  if (typeof THREAD_ID === 'undefined') return;

  const chatWindow = document.getElementById('chat-window');
  let lastId = 0;

  // Find the highest message id already rendered on page load
  document.querySelectorAll('.message[data-id]').forEach(function (el) {
    const id = parseInt(el.getAttribute('data-id'), 10);
    if (id > lastId) lastId = id;
  });

  function scrollToBottom() {
    if (chatWindow) chatWindow.scrollTop = chatWindow.scrollHeight;
  }
  scrollToBottom();

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
    } else {
      const bubble = document.createElement('div');
      bubble.className = 'message-bubble';

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

      const footer = document.createElement('div');
      footer.className = 'message-footer';

      const reactionBar = document.createElement('div');
      reactionBar.className = 'reaction-bar';
      const types = [['laugh','😂'],['cook','👨‍🍳'],['fraud','🚨'],['receipt','🧾']];
      types.forEach(function ([rtype, emoji]) {
        const btn = document.createElement('button');
        btn.className = 'reaction-btn' + (msg.user_reactions.includes(rtype) ? ' reacted' : '');
        btn.setAttribute('data-message-id', msg.id);
        btn.setAttribute('data-reaction', rtype);
        const count = msg.reactions[rtype] || '';
        btn.textContent = '';
        const countSpan = document.createElement('span');
        countSpan.className = 'reaction-count';
        countSpan.textContent = count;
        btn.appendChild(document.createTextNode(emoji + ' '));
        btn.appendChild(countSpan);
        btn.addEventListener('click', handleReaction);
        reactionBar.appendChild(btn);
      });
      footer.appendChild(reactionBar);

      const time = document.createElement('span');
      time.className = 'message-time';
      if (msg.created_at) {
        const d = new Date(msg.created_at);
        time.textContent = d.getHours().toString().padStart(2,'0') + ':' + d.getMinutes().toString().padStart(2,'0');
      }
      footer.appendChild(time);

      if (msg.can_delete) {
        const del = document.createElement('button');
        del.className = 'delete-btn';
        del.textContent = '✕';
        del.title = 'Delete';
        del.setAttribute('data-message-id', msg.id);
        del.addEventListener('click', handleDelete);
        footer.appendChild(del);
      }

      bubble.appendChild(footer);
      wrapper.appendChild(bubble);
    }
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
          // If an optimistic element with this body (from us) already exists, remove it
          // before appending the confirmed server-side version.
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
  // Pause polling when the tab is backgrounded; resume (+ immediate fetch) when it comes back
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) { pausePoll(); } else { pollMessages(); startPoll(); }
  });

  // ── Reaction handling ─────────────────────────────────────────────────────
  function handleReaction(e) {
    const btn = e.currentTarget;
    const messageId = btn.getAttribute('data-message-id');
    const reactionType = btn.getAttribute('data-reaction');

    fetch('/api/messages/' + messageId + '/react', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reaction_type: reactionType }),
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        const msgEl = document.getElementById('msg-' + messageId);
        if (!msgEl) return;
        msgEl.querySelectorAll('.reaction-btn').forEach(function (b) {
          const rt = b.getAttribute('data-reaction');
          const count = (data.counts && data.counts[rt]) || '';
          const countEl = b.querySelector('.reaction-count');
          if (countEl) countEl.textContent = count;
        });
        if (data.added) { btn.classList.add('reacted'); } else { btn.classList.remove('reacted'); }
      })
      .catch(function () {
        btn.classList.toggle('reacted');
        btn.style.opacity = '0.4';
        setTimeout(function () { btn.style.opacity = ''; }, 1500);
      });
  }

  document.querySelectorAll('.reaction-btn').forEach(function (btn) {
    btn.addEventListener('click', handleReaction);
  });

  // ── Delete handling ───────────────────────────────────────────────────────
  function handleDelete(e) {
    const btn = e.currentTarget;
    const messageId = btn.getAttribute('data-message-id');
    if (!confirm('Delete this message?')) return;
    fetch('/api/messages/' + messageId + '/delete', { method: 'POST' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        if (data.success) {
          const msgEl = document.getElementById('msg-' + messageId);
          if (msgEl) msgEl.remove();
        }
      })
      .catch(function () {
        const msgEl = document.getElementById('msg-' + messageId);
        const footer = msgEl && msgEl.querySelector('.message-footer');
        if (footer) {
          const errSpan = document.createElement('span');
          errSpan.style.cssText = 'color:var(--accent);font-size:0.75rem;margin-left:0.35rem';
          errSpan.textContent = 'Delete failed';
          footer.appendChild(errSpan);
          setTimeout(function () { errSpan.remove(); }, 2500);
        }
      });
  }

  document.querySelectorAll('.delete-btn').forEach(function (btn) {
    btn.addEventListener('click', handleDelete);
  });

  // ── Optimistic message send ───────────────────────────────────────────────
  // Intercepts the chat form submit, appends the message to the DOM immediately
  // (before the server responds), then confirms/rolls back based on the response.
  const chatForm     = document.getElementById('chat-form');
  const chatTextarea = document.getElementById('chat-input');
  const chatSendBtn  = document.getElementById('chat-send');
  let _pendingSeq = 0;

  function buildOptimisticEl(body, tempId) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message message-user message-mine message-pending';
    wrapper.id = tempId;
    wrapper.setAttribute('data-opt-body', body); // used by poll dedup

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    const text = document.createElement('div');
    text.className = 'message-text';
    text.textContent = body;
    bubble.appendChild(text);

    const footer = document.createElement('div');
    footer.className = 'message-footer';

    const time = document.createElement('span');
    time.className = 'message-time';
    const now = new Date();
    time.textContent = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
    footer.appendChild(time);

    const dot = document.createElement('span');
    dot.className = 'message-sending-dot';
    dot.setAttribute('aria-hidden', 'true');
    footer.appendChild(dot);

    bubble.appendChild(footer);
    wrapper.appendChild(bubble);
    return wrapper;
  }

  if (chatForm && chatTextarea) {
    chatForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const body = chatTextarea.value.trim();
      if (!body || !chatWindow) return;

      const tempId = 'opt-' + (++_pendingSeq);
      const optEl  = buildOptimisticEl(body, tempId);
      chatWindow.appendChild(optEl);
      scrollToBottom();

      // Clear input immediately — the key to feeling instant
      chatTextarea.value = '';
      chatTextarea.style.height = '';
      if (chatSendBtn) chatSendBtn.disabled = true;

      const fd = new FormData();
      fd.append('body', body);

      fetch(chatForm.action, {
        method: 'POST',
        headers: { 'X-Fetch': '1' },
        body: fd,
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (data) {
          // If the poll already appended the confirmed message, remove the optimistic dupe
          const confirmed = document.getElementById('msg-' + data.id);
          const el = document.getElementById(tempId);
          if (confirmed) {
            if (el) el.remove();
          } else if (el) {
            // Promote the optimistic element to a real one
            el.setAttribute('data-id', data.id);
            el.id = 'msg-' + data.id;
            el.removeAttribute('data-opt-body');
            el.classList.remove('message-pending');
            const dot = el.querySelector('.message-sending-dot');
            if (dot) dot.remove();
            if (data.id > lastId) lastId = data.id;
          }
        })
        .catch(function () {
          // Network / server error — remove optimistic element, restore the input
          const el = document.getElementById(tempId);
          if (el) el.remove();
          chatTextarea.value = body;
          if (chatSendBtn) chatSendBtn.disabled = false;
          chatTextarea.focus();
        });
    });
  }
})();
