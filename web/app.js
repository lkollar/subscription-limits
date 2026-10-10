'use strict';
const names = {claude: 'Claude Code', codex: 'Codex'};
const errors = {
  auth: 'Login expired or unavailable. Renew this provider’s login on the server.',
  timeout: 'the server could not fetch usage in time. Retrying automatically.',
  rateLimited: 'Provider rate limit reached. Retrying automatically.',
  collector: 'Usage could not be read. Check CodexBar on the server.'
};
const container = document.querySelector('#providers');
const connection = document.querySelector('#connection');
const button = document.querySelector('#refresh');
let snapshot = null;
let reachable = false;
let loading = false;
let offset = 0;
let notice = '';
const sections = {};
for (const id of Object.keys(names)) {
  const section = document.querySelector('#provider-template').content.firstElementChild.cloneNode(true);
  section.classList.add(id);
  section.setAttribute('aria-labelledby', `${id}-title`);
  section.querySelector('h2').id = `${id}-title`;
  section.querySelector('h2').textContent = names[id];
  container.append(section);
  sections[id] = section;
}
function validTime(value) { return typeof value === 'string' && Number.isFinite(Date.parse(value)); }
function remaining(value, now) {
  if (!validTime(value)) return 'Reset time unavailable';
  const seconds = Math.ceil((Date.parse(value) - now) / 1000);
  if (seconds <= 0) return 'Reset due · awaiting fresh usage';
  const mins = Math.ceil(seconds / 60);
  const days = Math.floor(mins / 1440);
  const hours = Math.floor((mins % 1440) / 60);
  const minutes = mins % 60;
  return `Resets in ${days ? `${days}d ` : ''}${hours ? `${hours}h ` : ''}${minutes}m`;
}
function localTime(value, now, weekday = true) {
  if (!validTime(value)) return '';
  const date = new Date(value);
  const today = date.toDateString() === new Date(now).toDateString();
  const clock = date.toLocaleTimeString(undefined, {hour:'2-digit', minute:'2-digit'});
  return today ? `Today, ${clock}` : date.toLocaleDateString(undefined,
    { ...(weekday ? {weekday:'short'} : {}), day:'numeric', month:'short',
      ...(date.getFullYear() !== new Date(now).getFullYear() ? {year:'numeric'} : {}) }) + `, ${clock}`;
}
function render() {
  const now = Date.now() + offset;
  container.setAttribute('aria-busy', String(loading && !snapshot));
  connection.textContent = notice || (!reachable ? (snapshot ? 'Offline · showing saved usage. Reconnect to refresh.' : 'Usage unavailable · reconnect to the server.') : snapshot?.refreshing ? 'Refreshing provider usage…' : 'Connected to the server · private via Tailscale');
  connection.classList.toggle('problem', !reachable);
  for (const [id, section] of Object.entries(sections)) {
    const provider = snapshot?.providers?.find(p => p.id === id);
    const hasData = validTime(provider?.lastSuccess);
    const expired = hasData && now - Date.parse(provider.lastSuccess) > (snapshot.staleAfterSeconds || 900) * 1000;
    const resetDue = Object.values(provider?.windows || {}).some(window => validTime(window?.resetsAt) && Date.parse(window.resetsAt) <= now);
    const stale = hasData && (!reachable || expired || resetDue || provider.status !== 'fresh');
    const status = section.querySelector('.status');
    status.textContent = !hasData ? 'Unavailable' : stale ? 'Stale' : 'Current';
    status.classList.toggle('problem', stale || !hasData);
    section.querySelector('.issue').textContent = errors[provider?.error] || (stale ? 'Current usage may differ from this last successful reading.' : !hasData ? (snapshot?.refreshing ? 'Waiting for the first successful refresh.' : 'No successful reading yet.') : '');
    for (const name of ['fiveHour', 'weekly']) {
      const row = section.querySelector(`[data-window="${name}"]`);
      const data = provider?.windows?.[name];
      const usable = hasData && data && Number.isFinite(data.usedPercent) && data.usedPercent >= 0 && data.usedPercent <= 100;
      const left = usable ? 100 - data.usedPercent : null;
      const percent = row.querySelector('.percentage');
      percent.replaceChildren();
      percent.append(document.createTextNode(usable ? `${Number(left.toFixed(1))}% ` : '— '));
      const small = document.createElement('small');
      small.textContent = usable ? 'left' : 'unavailable';
      percent.append(small);
      const progress = row.querySelector('progress');
      progress.hidden = !usable;
      progress.value = usable ? left : 0;
      progress.setAttribute('aria-label', `${names[id]} ${name === 'weekly' ? 'weekly' : 'five-hour'} remaining${stale ? ', stale' : ''}`);
      const exact = row.querySelector('.reset-time');
      const dated = usable && validTime(data.resetsAt) && Date.parse(data.resetsAt) > now;
      exact.textContent = dated ? localTime(data.resetsAt, now) : '';
      exact.hidden = !dated;
      if (dated) exact.dateTime = data.resetsAt;
      else exact.removeAttribute('datetime');
      row.querySelector('.countdown').textContent = usable ? remaining(data.resetsAt, now) : 'No window data available';
    }
    const resets = hasData ? provider?.savedResets : null;
    const known = resets && Number.isSafeInteger(resets.availableCount) && resets.availableCount >= 0;
    const details = section.querySelector('.saved-resets');
    details.hidden = !known;
    section.querySelector('.resets-unavailable').hidden = Boolean(known);
    if (known) {
      const expiries = Array.isArray(resets.expiresAt) ? resets.expiresAt : [];
      const due = expiries.some(expiry => validTime(expiry) && Date.parse(expiry) <= now);
      const old = stale || due;
      section.querySelector('.reset-count').textContent = `${resets.availableCount} ${old ? 'at last refresh' : 'available'} ›`;
      details.classList.toggle('problem', old);
      const valid = expiries.filter(validTime).sort((a,b) => Date.parse(a) - Date.parse(b));
      section.querySelector('.reset-hint').textContent = old ? 'Saved reset availability may have changed. Refresh to check.' :
        resets.availableCount === 0 ? 'No saved resets available.' : valid.length ?
        `Earliest expires ${localTime(valid[0], now, false)}. View only.` : 'Expiry dates unavailable. View only.';
      const list = section.querySelector('.reset-expiries');
      // Preserve expansion while countdowns update; only rebuild changed rows.
      const signature = JSON.stringify(expiries);
      if (list.dataset.expiries !== signature || list.dataset.day !== new Date(now).toDateString()) {
        list.dataset.expiries = signature;
        list.dataset.day = new Date(now).toDateString();
        list.replaceChildren();
        expiries.forEach((expiry, index) => {
          const row = document.createElement('li');
          const label = document.createElement('span'); label.textContent = `Reset ${index + 1}`;
          const time = document.createElement('time');
          time.textContent = validTime(expiry) ? `Expires ${localTime(expiry, now, false)}` : 'Expiry unavailable';
          if (validTime(expiry)) time.dateTime = expiry;
          row.append(label, time); list.append(row);
        });
      }
    }
    section.querySelector('.last-success').textContent = hasData ? `Last success · ${new Date(provider.lastSuccess).toLocaleString(undefined, {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})}` : 'Last success · never';
  }
}
async function load() {
  if (loading) return;
  loading = true;
  try {
    const response = await fetch('./api/usage', {cache:'no-store', signal:AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error('Server unavailable');
    const data = await response.json();
    if (!Array.isArray(data.providers)) throw new Error('Invalid usage');
    snapshot = data;
    reachable = true;
    if (validTime(data.serverTime)) offset = Date.parse(data.serverTime) - Date.now();
    try { localStorage.setItem('limits-last-good-v1', JSON.stringify(data)); } catch (_) { /* Storage may be disabled. */ }
  } catch (_) {
    reachable = false;
  } finally {
    loading = false;
    render();
  }
}
button.addEventListener('click', async () => {
  button.disabled = true;
  notice = '';
  try {
    const response = await fetch('./api/refresh', {method:'POST', signal:AbortSignal.timeout(10000)});
    if (response.status === 429) notice = 'Recently refreshed or refreshing · checking latest reading.';
    else if (!response.ok) throw new Error('Refresh unavailable');
    else notice = 'Refresh requested · checking provider usage…';
    await load();
    for (let i = 0; i < 20 && (i === 0 || snapshot?.refreshing); i++) {
      await new Promise(resolve => setTimeout(resolve, 5000));
      await load();
      if (!reachable) break;
    }
  } catch (_) { reachable = false; }
  finally { notice = ''; button.disabled = false; render(); }
});
try {
  const saved = JSON.parse(localStorage.getItem('limits-last-good-v1'));
  if (Array.isArray(saved?.providers)) snapshot = saved;
} catch (_) { /* No usable saved data. */ }
render();
load();
setInterval(load, 15000);
setInterval(render, 1000);
window.addEventListener('online', load);
window.addEventListener('offline', () => { reachable = false; notice = ''; render(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(() => {});
