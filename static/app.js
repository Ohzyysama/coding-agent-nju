const sessionListEl = document.getElementById('session-list');
const messagesEl = document.getElementById('messages');
const currentTitleEl = document.getElementById('current-title');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('send');
const newChatBtn = document.getElementById('new-chat');

let currentId = null;
let sending = false;

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function timeAgo(ts) {
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
  if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
  return Math.floor(diff / 86400) + ' 天前';
}

async function api(path, options) {
  const resp = await fetch(path, options);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || resp.statusText);
  }
  return resp;
}

function scrollBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/* ---------- 会话列表 ---------- */
async function loadSessions() {
  const sessions = await (await api('/api/sessions')).json();
  renderSessionList(sessions);
  if (!currentId && sessions.length > 0) {
    await selectSession(sessions[0].id);
  } else if (!currentId && sessions.length === 0) {
    await createSession();
  }
}

function renderSessionList(sessions) {
  sessionListEl.innerHTML = '';
  for (const s of sessions) {
    const li = document.createElement('li');
    li.className = 'session-item' + (s.id === currentId ? ' active' : '');
    li.dataset.id = s.id;

    const title = document.createElement('span');
    title.className = 'session-title';
    title.textContent = s.title;
    li.appendChild(title);

    const meta = document.createElement('div');
    meta.className = 'session-meta';
    meta.textContent = timeAgo(s.updated_at);
    li.appendChild(meta);

    const del = document.createElement('button');
    del.className = 'session-del';
    del.textContent = '×';
    del.title = '删除对话';
    del.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm('确定删除该对话？')) return;
      await api('/api/sessions/' + s.id, { method: 'DELETE' });
      if (s.id === currentId) {
        currentId = null;
        messagesEl.innerHTML = '';
        currentTitleEl.textContent = '选择一个对话开始';
      }
      await loadSessions();
    });
    li.appendChild(del);

    li.addEventListener('click', () => selectSession(s.id));
    sessionListEl.appendChild(li);
  }
}

async function selectSession(id) {
  currentId = id;
  const session = await (await api('/api/sessions/' + id)).json();
  currentTitleEl.textContent = session.title;
  renderHistory(session.messages);
  document.querySelectorAll('.session-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === id);
  });
  inputEl.focus();
}

async function createSession() {
  const data = await (await api('/api/sessions', { method: 'POST' })).json();
  await loadSessions();
  await selectSession(data.id);
}

/* ---------- 消息渲染 ---------- */
function appendUserBubble(text) {
  const div = document.createElement('div');
  div.className = 'msg user';
  div.textContent = text;
  messagesEl.appendChild(div);
  scrollBottom();
}

function appendAssistantBubble(text) {
  if (!text) return;
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.textContent = text;
  messagesEl.appendChild(div);
  scrollBottom();
}

function renderHistory(messages) {
  messagesEl.innerHTML = '';
  const hasContent = messages.some(m => m.role !== 'system');
  if (!hasContent) {
    const empty = document.createElement('div');
    empty.className = 'empty-hint';
    empty.textContent = '开始一个新的编程任务吧';
    messagesEl.appendChild(empty);
    return;
  }
  for (const m of messages) {
    if (m.role === 'system') continue;
    if (m.role === 'user') {
      appendUserBubble(m.content);
    } else if (m.role === 'assistant') {
      if (m.tool_calls) {
        for (const tc of m.tool_calls) {
          const chip = document.createElement('div');
          chip.className = 'tool-chip';
          chip.textContent = '🔧 ' + tc.function.name;
          messagesEl.appendChild(chip);
        }
      }
      if (m.content) appendAssistantBubble(m.content);
    } else if (m.role === 'tool') {
      const details = document.createElement('details');
      details.className = 'tool-result';
      const summary = document.createElement('summary');
      summary.textContent = '📄 执行结果';
      const pre = document.createElement('pre');
      pre.textContent = m.content;
      details.appendChild(summary);
      details.appendChild(pre);
      messagesEl.appendChild(details);
    }
  }
  scrollBottom();
}

/* ---------- 流式发送 ---------- */
async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || sending || !currentId) return;
  sending = true;
  sendBtn.disabled = true;
  inputEl.value = '';
  inputEl.style.height = 'auto';

  const hint = messagesEl.querySelector('.empty-hint');
  if (hint) hint.remove();

  appendUserBubble(text);

  const container = document.createElement('div');
  container.className = 'agent-progress';
  messagesEl.appendChild(container);
  let lastToolCard = null;

  try {
    const resp = await api('/api/sessions/' + currentId + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const dataLine = raw.split('\n').find(l => l.startsWith('data: '));
        if (!dataLine) continue;
        let evt;
        try { evt = JSON.parse(dataLine.slice(6)); } catch { continue; }
        lastToolCard = renderEvent(evt, container, lastToolCard);
      }
    }
  } catch (e) {
    const err = document.createElement('div');
    err.className = 'msg error';
    err.textContent = '出错：' + e.message;
    container.appendChild(err);
  }

  if (!container.hasChildNodes()) container.remove();
  sending = false;
  sendBtn.disabled = false;
  inputEl.focus();

  // 刷新会话列表（更新时间/标题），并同步标题栏
  await loadSessions();
  if (currentId) {
    const s = await (await api('/api/sessions/' + currentId)).json();
    currentTitleEl.textContent = s.title;
  }
}

async function respondConfirm(approved, allowBtn, denyBtn, statusEl) {
  allowBtn.disabled = true;
  denyBtn.disabled = true;
  statusEl.textContent = '处理中…';
  try {
    await api('/api/sessions/' + currentId + '/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved })
    });
    statusEl.textContent = approved ? '已允许' : '已拒绝';
  } catch (e) {
    statusEl.textContent = '确认失败：' + e.message;
  }
}

function renderEvent(evt, container, lastToolCard) {
  switch (evt.type) {
    case 'status': {
      container.querySelectorAll('.thinking').forEach(e => e.remove());
      const t = document.createElement('div');
      t.className = 'thinking';
      t.textContent = '正在思考…';
      container.appendChild(t);
      scrollBottom();
      return lastToolCard;
    }
    case 'tool_call': {
      const card = document.createElement('div');
      card.className = 'step-card';
      const head = document.createElement('div');
      head.className = 'step-head';
      head.textContent = '🔧 调用工具 ' + evt.name;
      card.appendChild(head);
      if (evt.args && Object.keys(evt.args).length) {
        const args = document.createElement('pre');
        args.className = 'step-args';
        args.textContent = JSON.stringify(evt.args, null, 2);
        card.appendChild(args);
      }
      const result = document.createElement('pre');
      result.className = 'step-result';
      result.textContent = '执行中…';
      card.appendChild(result);
      container.appendChild(card);
      scrollBottom();
      return card;
    }
    case 'tool_result': {
      if (lastToolCard) {
        const r = lastToolCard.querySelector('.step-result');
        if (r) { r.textContent = evt.content; r.classList.add('filled'); }
      }
      scrollBottom();
      return lastToolCard;
    }
    case 'answer': {
      container.querySelectorAll('.thinking').forEach(e => e.remove());
      const bubble = document.createElement('div');
      bubble.className = 'msg assistant';
      bubble.textContent = evt.content;
      container.appendChild(bubble);
      if (evt.tokens) {
        const stats = document.createElement('div');
        stats.className = 'token-stats';
        stats.textContent = '本次任务消耗 ' + evt.tokens + ' token';
        container.appendChild(stats);
      }
      scrollBottom();
      return lastToolCard;
    }
    case 'confirm': {
      container.querySelectorAll('.thinking').forEach(e => e.remove());
      const card = document.createElement('div');
      card.className = 'confirm-card';

      const text = document.createElement('div');
      text.className = 'confirm-text';
      text.textContent = '⚠️ Agent 请求执行危险命令：';

      const code = document.createElement('code');
      code.className = 'confirm-code';
      code.textContent = evt.command;

      const btns = document.createElement('div');
      btns.className = 'confirm-btns';

      const allowBtn = document.createElement('button');
      allowBtn.className = 'confirm-allow';
      allowBtn.textContent = '允许';

      const denyBtn = document.createElement('button');
      denyBtn.className = 'confirm-deny';
      denyBtn.textContent = '拒绝';

      const status = document.createElement('span');
      status.className = 'confirm-status';

      allowBtn.addEventListener('click', () => respondConfirm(true, allowBtn, denyBtn, status));
      denyBtn.addEventListener('click', () => respondConfirm(false, allowBtn, denyBtn, status));

      btns.appendChild(allowBtn);
      btns.appendChild(denyBtn);
      btns.appendChild(status);
      card.appendChild(text);
      card.appendChild(code);
      card.appendChild(btns);
      container.appendChild(card);
      scrollBottom();
      return lastToolCard;
    }
    case 'error': {
      container.querySelectorAll('.thinking').forEach(e => e.remove());
      const err = document.createElement('div');
      err.className = 'msg error';
      err.textContent = '出错：' + evt.content;
      container.appendChild(err);
      scrollBottom();
      return lastToolCard;
    }
  }
  return lastToolCard;
}

/* ---------- 事件绑定 ---------- */
newChatBtn.addEventListener('click', createSession);
sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
});

loadSessions();
