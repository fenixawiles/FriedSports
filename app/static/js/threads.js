// Thread polling and reaction handling
(function () {
  if (typeof THREAD_ID === 'undefined') return;

  const chatWindow = document.getElementById('chat-window');
  let lastId = 0;

  // Find the highest message id already rendered
  document.querySelectorAll('.message[data-id]').forEach(function (el) {
    const id = parseInt(el.getAttribute('data-id'), 10);
    if (id > lastId) lastId = id;
  });

  function scrollToBottom() {
    if (chatWindow) chatWindow.scrollTop = chatWindow.scrollHeight;
  }
  scrollToBottom();

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
        btn.innerHTML = emoji + ' <span class="reaction-count">' + count + '</span>';
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

  function pollMessages() {
    fetch('/api/threads/' + THREAD_ID + '/messages.json?after=' + lastId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.length) return;
        const wasAtBottom = chatWindow.scrollHeight - chatWindow.scrollTop <= chatWindow.clientHeight + 60;
        data.forEach(function (msg) {
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

  setInterval(pollMessages, 8000);

  // Reaction handling
  function handleReaction(e) {
    const btn = e.currentTarget;
    const messageId = btn.getAttribute('data-message-id');
    const reactionType = btn.getAttribute('data-reaction');

    fetch('/api/messages/' + messageId + '/react', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reaction_type: reactionType }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        // Update all reaction buttons in this message's bar
        const msgEl = document.getElementById('msg-' + messageId);
        if (!msgEl) return;
        const btns = msgEl.querySelectorAll('.reaction-btn');
        btns.forEach(function (b) {
          const rt = b.getAttribute('data-reaction');
          const count = data.counts[rt] || '';
          const countEl = b.querySelector('.reaction-count');
          if (countEl) countEl.textContent = count;
        });
        // Toggle reacted class on clicked button
        if (data.added) {
          btn.classList.add('reacted');
        } else {
          btn.classList.remove('reacted');
        }
      })
      .catch(function () {});
  }

  // Wire up existing reaction buttons
  document.querySelectorAll('.reaction-btn').forEach(function (btn) {
    btn.addEventListener('click', handleReaction);
  });

  // Delete handling
  function handleDelete(e) {
    const btn = e.currentTarget;
    const messageId = btn.getAttribute('data-message-id');
    if (!confirm('Delete this message?')) return;
    fetch('/api/messages/' + messageId + '/delete', { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          const msgEl = document.getElementById('msg-' + messageId);
          if (msgEl) msgEl.remove();
        }
      })
      .catch(function () {});
  }

  document.querySelectorAll('.delete-btn').forEach(function (btn) {
    btn.addEventListener('click', handleDelete);
  });

  // Submit form via enter (shift+enter for newline)
  const chatInput = document.getElementById('chat-input');
  if (chatInput) {
    chatInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('chat-form').submit();
      }
    });
  }
})();
