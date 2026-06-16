/* Investment Assistant K8s — WebSocket Chat Client */

const SESSION_ID = localStorage.getItem('session_id') || crypto.randomUUID();
localStorage.setItem('session_id', SESSION_ID);

let ws = null;
let currentAssistantBubble = null;
let currentAssistantText = '';
let reconnectTimer = null;
let reconnectDelay = 1000;
const MAX_RECONNECT = 30000;
let latestPortfolioDashboard = null;

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
  appendChatMessage('user', text);
}

function appendChatMessage(role, text, createdAt = null) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  const body = role === 'assistant' ? markdownToHtml(text) : escapeHtml(text);
  div.innerHTML = `
    <div class="msg-bubble">${body}</div>
    <div class="msg-time">${createdAt ? formatTime(createdAt) : timeNow()}</div>`;
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
  div.innerHTML = `<div class="msg-bubble" style="border-color:#ef4444;color:#ef4444;">Error: ${escapeHtml(msg)}</div>`;
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
      html += `
        <div class="market-row">
          <span class="name">${name}</span>
          <span class="price ${cls}">${price}${chgStr}</span>
        </div>`;
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

async function loadChatHistory() {
  try {
    const resp = await fetch(`/api/chat/${SESSION_ID}/messages?limit=200`);
    if (!resp.ok) throw new Error(`history ${resp.status}`);
    const history = await resp.json();
    if (!history.length) {
      appendWelcomeMessage();
      return;
    }
    for (const msg of history) {
      appendChatMessage(msg.role, msg.content, msg.created_at);
    }
  } catch (e) {
    appendWelcomeMessage();
  }
}

// ── Workspace views ──────────────────────────────────────────────────────────

function showView(view) {
  const isChat = view === 'chat';
  document.getElementById('messages').classList.toggle('hidden', !isChat);
  document.getElementById('chat-input-area').classList.toggle('hidden', !isChat);
  document.getElementById('portfolio-view').classList.toggle('hidden', view !== 'portfolio');
  document.getElementById('nav-chat').classList.toggle('active', isChat);
  document.getElementById('nav-portfolio').classList.toggle('active', view === 'portfolio');
  if (view === 'portfolio') loadPortfolioDashboard();
}

// ── Portfolio dashboard ──────────────────────────────────────────────────────

async function loadPortfolioDashboard() {
  const updated = document.getElementById('portfolio-updated');
  updated.textContent = 'Loading portfolio state…';
  try {
    const resp = await fetch('/api/portfolio/dashboard');
    const data = await resp.json();
    latestPortfolioDashboard = data;
    renderPortfolioDashboard(data);
  } catch (e) {
    updated.textContent = 'Could not load portfolio dashboard.';
    document.getElementById('allocation-list').innerHTML =
      '<div class="empty-state">Portfolio service is unavailable.</div>';
  }
}

function renderPortfolioDashboard(data) {
  const normalized = normalizePortfolio(data.summary || {});
  const total = normalized.holdings.reduce((sum, row) => sum + (row.value || 0), 0);
  const errors = normalized.brokers.filter(b => b.error).length + (data.summary?.error ? 1 : 0);

  document.getElementById('portfolio-total').textContent = formatCurrency(total);
  document.getElementById('portfolio-holdings-count').textContent = normalized.holdings.length;
  document.getElementById('portfolio-brokers-count').textContent = normalized.brokers.length;
  document.getElementById('portfolio-errors-count').textContent = errors;
  document.getElementById('portfolio-updated').textContent =
    `Updated ${formatTime(data.timestamp || data.summary?.timestamp || new Date().toISOString())}`;

  renderAllocation(normalized.holdings, total);
  renderBrokers(normalized.brokers, data.summary);
  renderHoldings(normalized.holdings);
  renderPortfolioTrades(data.trades || []);
}

function normalizePortfolio(summary) {
  const brokers = summary.brokers || {};
  const holdings = [];
  const brokerRows = [];

  for (const [broker, payload] of Object.entries(brokers)) {
    const error = payload?.error || null;
    const sourceRows = Array.isArray(payload?.positions)
      ? payload.positions
      : Array.isArray(payload?.balances)
        ? payload.balances
        : [];

    brokerRows.push({ broker, count: sourceRows.length, error });

    for (const row of sourceRows) {
      const quantity = numberOrNull(row.qty ?? row.quantity ?? row.position ?? row.available ?? row.free);
      const locked = numberOrNull(row.locked);
      const totalQuantity = quantity == null && locked != null ? locked : (quantity || 0) + (locked || 0);
      const price = numberOrNull(row.current_price ?? row.price ?? row.avg_entry_price ?? row.avg_cost);
      const value = numberOrNull(row.market_value ?? row.value_usd ?? row.usd_value)
        ?? (price != null && totalQuantity ? price * totalQuantity : null);
      holdings.push({
        broker,
        symbol: row.symbol || row.currency || row.asset || 'Unknown',
        quantity: totalQuantity || quantity || 0,
        price,
        value,
        pnl: numberOrNull(row.unrealized_pl ?? row.pnl_usd),
        pnlPct: numberOrNull(row.unrealized_plpc),
      });
    }
  }

  if (!Object.keys(brokers).length && summary.error) {
    brokerRows.push({ broker: summary.tool || 'portfolio', count: 0, error: summary.error });
  }

  holdings.sort((a, b) => (b.value || 0) - (a.value || 0));
  return { brokers: brokerRows, holdings };
}

function renderAllocation(holdings, total) {
  const el = document.getElementById('allocation-list');
  const valued = holdings.filter(row => row.value && row.value > 0);
  if (!valued.length || total <= 0) {
    el.innerHTML = [
      '<div class="empty-state">',
      'No priced holdings available. Connect broker credentials or enable external API access ',
      'to calculate allocation.',
      '</div>',
    ].join('');
    return;
  }
  el.innerHTML = valued.slice(0, 12).map(row => {
    const pct = (row.value / total) * 100;
    return `
      <div class="allocation-row">
        <span>${escapeHtml(row.symbol)}</span>
        <strong>${pct.toFixed(1)}%</strong>
        <span class="allocation-bar"><span class="allocation-fill" style="width:${pct}%"></span></span>
      </div>`;
  }).join('');
}

function renderBrokers(brokers, summary) {
  const el = document.getElementById('broker-list');
  if (summary?.error && !brokers.length) {
    el.innerHTML = `
      <div class="broker-row">
        <span>Portfolio</span>
        <span class="status-error">${escapeHtml(summary.error)}</span>
      </div>`;
    return;
  }
  if (!brokers.length) {
    el.innerHTML = '<div class="empty-state">No broker data returned.</div>';
    return;
  }
  el.innerHTML = brokers.map(row => `
    <div class="broker-row">
      <span>${escapeHtml(row.broker)}</span>
      <span class="${row.error ? 'status-error' : 'status-ok'}">
        ${row.error ? escapeHtml(row.error) : `${row.count} holdings`}
      </span>
    </div>`).join('');
}

function renderHoldings(holdings) {
  const el = document.getElementById('holdings-table');
  if (!holdings.length) {
    el.innerHTML = '<tr><td colspan="6" class="empty-state">No holdings available.</td></tr>';
    return;
  }
  el.innerHTML = holdings.map(row => `
    <tr>
      <td>${escapeHtml(row.symbol)}</td>
      <td>${escapeHtml(row.broker)}</td>
      <td>${formatNumber(row.quantity)}</td>
      <td>${formatCurrency(row.price)}</td>
      <td>${formatCurrency(row.value)}</td>
      <td class="${(row.pnl || 0) >= 0 ? 'up' : 'down'}">
        ${formatCurrency(row.pnl)}${row.pnlPct != null ? ` (${(row.pnlPct * 100).toFixed(2)}%)` : ''}
      </td>
    </tr>`).join('');
}

function renderPortfolioTrades(trades) {
  const el = document.getElementById('portfolio-trades-table');
  if (!trades.length) {
    el.innerHTML = '<div class="empty-state">No recent trades recorded.</div>';
    return;
  }
  el.innerHTML = trades.map(t => `
    <div class="compact-row">
      <span>
        <strong class="trade-side-${t.side}">${String(t.side || '').toUpperCase()}</strong>
        ${escapeHtml(t.symbol)} x${formatNumber(t.quantity)}
      </span>
      <span>${escapeHtml(t.broker)} · ${escapeHtml(t.status)}</span>
    </div>`).join('');
}

function askAboutPortfolio() {
  showView('chat');
  sendQuick(
    'Analyse my current portfolio. Use the portfolio summary, recent trades, market data, ' +
    'and news context. Explain allocation, concentration risk, P&L drivers, and practical ' +
    'rebalancing ideas.'
  );
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
function formatTime(value) {
  try {
    return new Date(value).toLocaleString([], {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch (_) {
    return timeNow();
  }
}
function numberOrNull(value) {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
function formatNumber(value) {
  const n = numberOrNull(value);
  if (n == null) return 'N/A';
  return n.toLocaleString(undefined, { maximumFractionDigits: 6 });
}
function formatCurrency(value) {
  const n = numberOrNull(value);
  if (n == null) return 'N/A';
  return n.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
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

function appendWelcomeMessage() {
  const welcome = document.createElement('div');
  welcome.className = 'msg assistant';
  welcome.innerHTML = `
    <div class="msg-bubble">
      <strong>Welcome to Investment Assistant — Multi-Agent Edition</strong><br><br>
      I coordinate specialised services running on AWS EKS:<br>
      <strong>Market Data</strong> · <strong>News</strong> · <strong>Portfolio</strong> ·
      <strong>Simulation</strong> · <strong>Scheduler</strong><br><br>
      Ask about markets, your portfolio, recent news, simulations, or reports. This browser keeps
      a session id in local storage, and the gateway reloads your persisted chat history when you return.
    </div>
    <div class="msg-time">${timeNow()}</div>`;
  messagesEl().appendChild(welcome);
}

// ── Init ──────────────────────────────────────────────────────────────────────

globalThis.addEventListener('DOMContentLoaded', async () => {
  connect();
  await loadChatHistory();
  loadSnapshot();
  loadTrades();
  loadPortfolioDashboard();
  checkAgentHealth();
  setInterval(loadSnapshot, 5 * 60 * 1000);
  setInterval(loadTrades, 30 * 1000);
  setInterval(checkAgentHealth, 60 * 1000);
  setSendEnabled(true);

});
