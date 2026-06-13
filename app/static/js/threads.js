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

      if (msg.type === 'user' && !msg.is_mine) {
        const rep = document.createElement('button');
        rep.className = 'report-btn';
        rep.textContent = '⚑';
        rep.title = 'Report message';
        rep.setAttribute('aria-label', 'Report message');
        rep.setAttribute('data-message-id', msg.id);
        if (msg.author_id) rep.setAttribute('data-author-id', msg.author_id);
        rep.setAttribute('data-author-name', msg.author || 'this user');
        rep.addEventListener('click', handleReportClick);
        footer.appendChild(rep);
      }

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
      if (chatSendBtn) { chatSendBtn.disabled = true; chatSendBtn.classList.add('sending'); }

      const fd = new FormData();
      fd.append('body', body);

      fetch(chatForm.action, {
        method: 'POST',
        headers: { 'X-Fetch': '1' },
        body: fd,
      })
        .then(function (r) {
          return r.json().then(function (j) {
            if (!r.ok) {
              var e = new Error(r.status);
              e.serverMessage = j && j.message;   // e.g. content-filter reason
              throw e;
            }
            return j;
          });
        })
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
        .catch(function (err) {
          // Network / server error — remove optimistic element, restore the input
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
          // Revert the send button from spinner back to the arrow
          if (chatSendBtn) chatSendBtn.classList.remove('sending');
        });

      // First take removes the empty state
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

  // ── Group vote: Confirm / Dismiss / Redeemed — optimistic toggle ──────────
  const voteRow = document.getElementById('icard-vote-row');
  if (voteRow) {
    let voteBusy = false;

    function setVoteNum(type, n) {
      document.querySelectorAll(
        '[data-vote-num="' + type + '"], [data-ctx-vote="' + type + '"]'
      ).forEach(function (el) { el.textContent = n; });
    }
    function getVoteNum(type) {
      const el = voteRow.querySelector('[data-vote-num="' + type + '"]');
      return el ? parseInt(el.textContent, 10) || 0 : 0;
    }

    voteRow.addEventListener('click', function (e) {
      const btn = e.target.closest('.vote-btn');
      if (!btn || voteBusy) return;
      voteBusy = true;

      const voteType = btn.getAttribute('data-vote');
      const wasActive = btn.classList.contains('active');
      const prevActive = voteRow.querySelector('.vote-btn.active');
      const prevType = prevActive ? prevActive.getAttribute('data-vote') : null;

      // Optimistic update: one vote per user — switching moves the count
      const snapshot = {};
      ['confirm', 'dismiss', 'redeem'].forEach(function (t) { snapshot[t] = getVoteNum(t); });

      if (prevActive) {
        prevActive.classList.remove('active');
        setVoteNum(prevType, Math.max(0, getVoteNum(prevType) - 1));
      }
      if (!wasActive) {
        btn.classList.add('active');
        setVoteNum(voteType, getVoteNum(voteType) + 1);
      }

      fetch('/api/threads/' + THREAD_ID + '/vote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ vote_type: voteType }),
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (data) {
          // Reconcile with authoritative counts
          ['confirm', 'dismiss', 'redeem'].forEach(function (t) {
            setVoteNum(t, data.votes[t] || 0);
          });
          voteRow.querySelectorAll('.vote-btn').forEach(function (b) {
            b.classList.toggle('active', b.getAttribute('data-vote') === data.user_vote);
          });
          if (typeof showToast === 'function') {
            showToast(data.user_vote ? 'Vote recorded' : 'Vote removed', 'success');
          }
        })
        .catch(function () {
          // Revert to snapshot
          ['confirm', 'dismiss', 'redeem'].forEach(function (t) { setVoteNum(t, snapshot[t]); });
          voteRow.querySelectorAll('.vote-btn').forEach(function (b) {
            b.classList.toggle('active', b.getAttribute('data-vote') === prevType);
          });
          if (typeof showToast === 'function') showToast('Vote failed — try again', 'error');
        })
        .finally(function () { voteBusy = false; });
    });
  }

  // ── Report a message + block its author ───────────────────────────────────
  const reportSheet   = document.getElementById('report-sheet');
  let   reportTarget  = { messageId: null, authorId: null, authorName: null };

  function handleReportClick(e) {
    const btn = e.currentTarget || e.target.closest('.report-btn');
    if (!btn || !reportSheet) return;
    reportTarget = {
      messageId:  btn.getAttribute('data-message-id'),
      authorId:   btn.getAttribute('data-author-id') || null,
      authorName: btn.getAttribute('data-author-name') || 'this user',
    };
    const blockBtn = document.getElementById('report-block-btn');
    if (blockBtn) {
      blockBtn.textContent = 'Block ' + reportTarget.authorName;
      blockBtn.style.display = reportTarget.authorId ? '' : 'none';
    }
    reportSheet.hidden = false;
  }

  function closeReportSheet() {
    if (reportSheet) reportSheet.hidden = true;
  }

  if (reportSheet) {
    // Submit a report under the chosen category
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

    // Block the author — posts the hidden form to /friends/block/<id>
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

  // Wire the report buttons present on initial render
  document.querySelectorAll('.report-btn').forEach(function (btn) {
    btn.addEventListener('click', handleReportClick);
  });
})();
