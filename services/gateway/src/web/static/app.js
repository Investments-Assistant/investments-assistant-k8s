/* Investment Assistant K8s — WebSocket Chat Client */

const SESSION_ID = localStorage.getItem('session_id') || crypto.randomUUID();
localStorage.setItem('session_id', SESSION_ID);

let ws = null;
let currentAssistantBubble = null;
let currentAssistantText = '';
let reconnectTimer = null;
let reconnectDelay = 1000;
const MAX_RECONNECT = 30000;

// Map tool names to the owning agent for display
const TOOL_AGENTS = {
  get_stock_data: 'market-data', get_crypto_data: 'market-data',
  get_market_overview: 'market-data', get_technical_indicators: 'market-data',
  get_options_chain: 'market-data', search_ticker: 'market-data',
  get_earnings_calendar: 'market-data',
  search_market_news: 'news', search_stored_news: 'news', get_latest_news: 'news',
  get_portfolio_summary: 'portfolio', get_account_info: 'portfolio',
  get_trade_history: 'portfolio', execute_trade: 'portfolio',
  confirm_trade: 'portfolio', cancel_order: 'portfolio',
  run_simulation: 'simulation',
  generate_report: 'scheduler',
  set_trading_mode: 'gateway',
};

// ── WebSocket ──────────────────────────────────────────────────────────��───────

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${location.host}/ws/chat/${SESSION_ID}`;
  setStatus('connecting');
  ws = new WebSocket(url);

  ws.onopen = () => {
    setStatus('online');
    setDot('gateway', true);
    reconnectDelay = 1000;
    clearTimeout(reconnectTimer);
  };

  ws.onclose = (e) => {
    setStatus('offline');
    setDot('gateway', false);
    if (e.code !== 1000) {
      reconnectTimer = setTimeout(() => {
        reconnectDelay = Math.min(reconnectDelay * 1.5, MAX_RECONNECT);
        connect();
      }, reconnectDelay);
    }
  };

  ws.onerror = (e) => console.error('WS error', e);
  ws.onmessage = (e) => handleEvent(JSON.parse(e.data));
}

function handleEvent(event) {
  switch (event.type) {
    case 'text_delta':   appendAssistantDelta(event.text); break;
    case 'tool_call':    appendToolCall(event.name, event.input); break;
    case 'tool_result':  appendToolResult(event.name, event.result); break;
    case 'done':         finaliseAssistantMessage(); setSendEnabled(true); break;
    case 'error':        appendErrorMessage(event.message); setSendEnabled(true); break;
  }
}

// ── Message rendering ─────────────────────────────────────────────────────────

function appendUserMessage(text) {
  const div = document.createElement('div');
  div.className = 'msg user';
  div.innerHTML = `
    <div class="msg-bubble">${escapeHtml(text)}</div>
    <div class="msg-time">${timeNow()}</div>`;
  messagesEl().appendChild(div);
  scrollBottom();
}

function startAssistantMessage() {
  currentAssistantText = '';
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = `
    <div class="msg-bubble" id="streaming-bubble">
      <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
    </div>
    <div class="msg-time">${timeNow()}</div>`;
  messagesEl().appendChild(div);
  currentAssistantBubble = div.querySelector('#streaming-bubble');
  currentAssistantBubble.removeAttribute('id');
  scrollBottom();
}

function appendAssistantDelta(text) {
  if (!currentAssistantBubble) startAssistantMessage();
  currentAssistantText += text;
  currentAssistantBubble.innerHTML = markdownToHtml(currentAssistantText);
  scrollBottom();
}

function finaliseAssistantMessage() {
  if (currentAssistantBubble && currentAssistantText) {
    currentAssistantBubble.innerHTML = markdownToHtml(currentAssistantText);
  }
  currentAssistantBubble = null;
  currentAssistantText = '';
  scrollBottom();
}

function appendToolCall(name, input) {
  const agent = TOOL_AGENTS[name] || 'agent';
  // Light up the agent dot while it's working
  setDot(agentDotKey(agent), true);
  const el = document.createElement('div');
  el.className = 'tool-call';
  el.setAttribute('data-tool', name);
  el.innerHTML = `
    <span class="tool-icon">🔧</span>
    Calling <strong>${escapeHtml(name)}</strong>…
    <span class="agent-tag">${agent}</span>`;
  messagesEl().appendChild(el);
  scrollBottom();
}

function appendToolResult(name, resultStr) {
  let preview = resultStr;
  try {
    const obj = JSON.parse(resultStr);
    preview = JSON.stringify(obj, null, 0).slice(0, 120) + (resultStr.length > 120 ? '…' : '');
  } catch (_) { /* raw string */ }
  const el = document.createElement('div');
  el.className = 'tool-call result';
  el.innerHTML = `
    <span class="tool-icon">✅</span>
    <strong>${escapeHtml(name)}</strong> → ${escapeHtml(preview)}`;
  messagesEl().appendChild(el);
  scrollBottom();
}

function appendErrorMessage(msg) {
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = `<div class="msg-bubble" style="border-color:#ef4444;color:#ef4444;">⚠️ Error: ${escapeHtml(msg)}</div>`;
  messagesEl().appendChild(div);
  scrollBottom();
}

// ── Send ──────────────────────────────────────────────────────────────────────

function sendMessage() {
  const input = document.getElementById('user-input');
  const text = input.value.trim();
  if (!text || ws?.readyState !== WebSocket.OPEN) return;
  input.value = '';
  input.style.height = '';
  setSendEnabled(false);
  appendUserMessage(text);
  startAssistantMessage();
  ws.send(JSON.stringify({ message: text }));
}

function sendQuick(text) {
  document.getElementById('user-input').value = text;
  sendMessage();
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  const ta = e.target;
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
}

// ── Trading mode ───────────────────────────────────────────────────────────────

async function setMode(mode) {
  document.getElementById('btn-recommend').classList.toggle('active', mode === 'recommend');
  document.getElementById('btn-auto').classList.toggle('active', mode === 'auto');
  const statusEl = document.getElementById('mode-status');
  statusEl.textContent = mode === 'auto'
    ? '⚡ Auto mode — agent executes within safety limits.'
    : '✋ Recommend mode — agent proposes, you confirm.';
  if (ws?.readyState === WebSocket.OPEN) {
    setSendEnabled(false);
    appendUserMessage(`Switch trading mode to ${mode}`);
    startAssistantMessage();
    ws.send(JSON.stringify({ message: `Switch trading mode to ${mode}` }));
  }
}

// ── Market snapshot ────────────────────────────────────────────────────────────

async function loadSnapshot() {
  const el = document.getElementById('market-snapshot');
  el.textContent = 'Loading…';
  try {
    const resp = await fetch('/api/market/snapshot');
    const data = await resp.json();
    if (data.message) { el.textContent = data.message; return; }
    const markets = data.markets || {};
    let html = '';
    for (const [name, info] of Object.entries(markets)) {
      const price = info.price ? info.price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : 'N/A';
      const chg = info.change_pct;
      const cls = chg > 0 ? 'up' : chg < 0 ? 'down' : '';
      const sign = chg > 0 ? '+' : '';
      const chgStr = chg == null ? '' : ` (${sign}${chg}%)`;
      html += `<div class="market-row"><span class="name">${name}</span><span class="price ${cls}">${price}${chgStr}</span></div>`;
    }
    el.innerHTML = html || 'No data available';
  } catch (e) {
    el.textContent = 'Failed to load snapshot.';
  }
}

async function loadTrades() {
  const el = document.getElementById('trades-list');
  try {
    const resp = await fetch('/api/trades?limit=5');
    const trades = await resp.json();
    if (!trades.length) { el.textContent = 'No trades yet.'; return; }
    el.innerHTML = trades.map(t => `
      <div class="report-item">
        <span><span class="trade-side-${t.side}">${t.side.toUpperCase()}</span> ${t.symbol} ×${t.quantity}</span>
        <span style="font-size:0.68rem;color:var(--text-muted)">${t.broker}</span>
      </div>`).join('');
  } catch (e) {
    el.textContent = 'Could not load trades.';
  }
}

// ── Agent health check ─────────────────────────────────────────────────────────

async function checkAgentHealth() {
  try {
    const resp = await fetch('/api/health');
    if (resp.ok) {
      const data = await resp.json();
      // Gateway is up if health responded — mark all dots online
      // (individual service checks happen via the gateway health endpoint)
      setDot('market', true);
      setDot('news', true);
      setDot('portfolio', true);
      setDot('simulation', true);
      setDot('scheduler', true);
    }
  } catch (_) {}
}

// ── Utilities ────────────────────────────────────────────────────────────────���─

function agentDotKey(agent) {
  const map = {
    'market-data': 'market', 'news': 'news', 'portfolio': 'portfolio',
    'simulation': 'simulation', 'scheduler': 'scheduler', 'gateway': 'gateway',
  };
  return map[agent] || 'gateway';
}

function setDot(key, online) {
  const el = document.getElementById(`dot-${key}`);
  if (el) {
    el.classList.toggle('online', online);
    el.classList.toggle('offline', !online);
  }
}

function messagesEl() { return document.getElementById('messages'); }
function scrollBottom() { const el = messagesEl(); el.scrollTop = el.scrollHeight; }
function setSendEnabled(e) {
  document.getElementById('send-btn').disabled = !e;
  document.getElementById('user-input').disabled = !e;
}
function setStatus(state) {
  const el = document.getElementById('connection-status');
  el.className = 'conn-status ' + state;
  el.textContent = state === 'online' ? 'Connected' : state === 'connecting' ? 'Connecting…' : 'Disconnected';
}
function timeNow() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function escapeHtml(str) {
  return String(str)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;').replaceAll('"', '&quot;');
}

function replaceCodeBlocks(html) {
  const FENCE = '```';
  let result = '', pos = 0;
  while (pos < html.length) {
    const open = html.indexOf(FENCE, pos);
    if (open === -1) { result += html.slice(pos); break; }
    result += html.slice(pos, open);
    const bodyStart = open + FENCE.length;
    const close = html.indexOf(FENCE, bodyStart);
    if (close === -1) { result += html.slice(open); break; }
    const body = html.slice(bodyStart, close);
    const nl = body.indexOf('\n');
    const code = (nl >= 0 ? body.slice(nl + 1) : body).trim();
    result += `<pre><code>${code}</code></pre>`;
    pos = close + FENCE.length;
  }
  return result;
}

function markdownToHtml(md) {
  let html = escapeHtml(md);
  html = replaceCodeBlocks(html);
  html = html.replaceAll(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replaceAll(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replaceAll(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replaceAll(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replaceAll(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replaceAll(/^# (.+)$/gm, '<h1>$1</h1>');
  html = html.replaceAll(/^[-*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)+/s, '<ul>$&</ul>');
  html = html.replaceAll(/^\d+\. (.+)$/gm, '<li>$1</li>');
  html = html.replaceAll(/^---$/gm, '<hr>');
  html = html.replaceAll(/\n\n+/g, '</p><p>');
  html = html.replaceAll('\n', '<br>');
  return `<p>${html}</p>`;
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('hidden');
}

// ── Init ──────────────────────────────────────────────────────────────────────

globalThis.addEventListener('DOMContentLoaded', () => {
  connect();
  loadSnapshot();
  loadTrades();
  checkAgentHealth();
  setInterval(loadSnapshot, 5 * 60 * 1000);
  setInterval(loadTrades, 30 * 1000);
  setInterval(checkAgentHealth, 60 * 1000);
  setSendEnabled(true);

  const welcome = document.createElement('div');
  welcome.className = 'msg assistant';
  welcome.innerHTML = `
    <div class="msg-bubble">
      <strong>Welcome to Investment Assistant — Multi-Agent Edition 📈</strong><br><br>
      I coordinate a fleet of 6 specialised agents running on AWS EKS:<br>
      <strong>Market Data</strong> · <strong>News</strong> · <strong>Portfolio</strong> ·
      <strong>Simulation</strong> · <strong>Scheduler</strong><br><br>
      I have access to real-time market data, sentiment analysis, and your brokerage accounts
      (Alpaca, Interactive Brokers, Coinbase, Binance).<br><br>
      Use the quick prompts on the left or ask me anything.
    </div>
    <div class="msg-time">${timeNow()}</div>`;
  messagesEl().appendChild(welcome);
});
