/* A股智能分析 - 共享JS工具库 */

const API_BASE = '/api';

// ======== API 调用 ========
async function apiGet(path) {
  try {
    const resp = await fetch(`${API_BASE}${path}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (e) {
    console.error(`API GET ${path} failed:`, e);
    return { error: e.message };
  }
}

// ======== 数值格式化 ========
function fmtPct(v) {
  if (v === undefined || v === null || v === '—') return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function fmtPrice(v) {
  if (v === undefined || v === null || v === '—') return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return n.toFixed(2);
}

function pctClass(v) {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (n > 0) return 'up';
  if (n < 0) return 'down';
  return 'flat';
}

function pctBadge(v) {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (n > 0) return '<span class="badge badge-up">' + fmtPct(v) + '</span>';
  if (n < 0) return '<span class="badge badge-down">' + fmtPct(v) + '</span>';
  return '<span class="badge" style="background:rgba(144,144,168,0.15);color:var(--text-secondary)">0.00%</span>';
}

// ======== 导航高亮 ========
function setActiveNav(pageId) {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.page === pageId);
  });
}

// ======== 自选股管理 ========
function getWatchlist() {
  try {
    return JSON.parse(localStorage.getItem('watchlist') || '[]');
  } catch { return []; }
}

function saveWatchlist(list) {
  localStorage.setItem('watchlist', JSON.stringify(list));
}

function addToWatchlist(stock) {
  const list = getWatchlist();
  if (list.some(s => s.code === stock.code)) return false;
  list.push({ code: stock.code, name: stock.name, addedAt: new Date().toISOString() });
  saveWatchlist(list);
  return true;
}

function removeFromWatchlist(code) {
  const list = getWatchlist().filter(s => s.code !== code);
  saveWatchlist(list);
}

function isInWatchlist(code) {
  return getWatchlist().some(s => s.code === code);
}
