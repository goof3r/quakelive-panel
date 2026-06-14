/* ============================================================
   Quake Live Panel — panel.js
   ============================================================ */

// ── Dashboard ──────────────────────────────────────────────
function startDashboard(serverIds) {
    refreshDashboard(serverIds);
    setInterval(() => refreshDashboard(serverIds), 15000);
}

function refreshDashboard(serverIds) {
    const ts = new Date().toLocaleTimeString('pl-PL');
    const el = document.getElementById('last-refresh');
    if (el) el.textContent = 'Ostatni refresh: ' + ts;

    fetch('/api/status')
        .then(r => r.json())
        .then(data => {
            if (!data.ok) return;
            serverIds.forEach(id => {
                const s = data.servers[id];
                if (!s) return;
                updateServerCard(id, s);
            });
            if (data.logs) updateAuditLog(data.logs);
        })
        .catch(() => {});
}

function updateServerCard(id, s) {
    const dot    = document.getElementById('dot-'    + id);
    const status = document.getElementById('status-' + id);
    const map    = document.getElementById('map-'    + id);
    const gt     = document.getElementById('gt-'     + id);
    const pl     = document.getElementById('pl-'     + id);
    const plnum  = document.getElementById('plnum-'  + id);
    const plmax  = document.getElementById('plmax-'  + id);
    const bar    = document.getElementById('bar-'    + id);
    const card   = document.getElementById('srv-'    + id);

    const running = s.running;
    const info    = s.info || {};
    const cur     = info.players_cur ?? (s.players?.length ?? 0);
    const max     = info.players_max ?? 0;

    if (dot) {
        dot.className = 'status-dot ' + (running ? 'online' : 'offline');
    }
    if (status) {
        status.innerHTML = running
            ? '<span class="badge-online">● ONLINE</span>'
            : '<span class="badge-offline">○ OFFLINE</span>';
    }
    if (card) {
        card.className = 'server-card' + (running ? '' : ' offline');
    }
    if (map)   map.textContent   = info.map       || (running ? '—' : 'offline');
    if (gt)    gt.textContent    = info.gametype   || '—';
    if (pl)    pl.textContent    = running ? cur + '/' + max : '—';
    if (plnum) plnum.textContent = cur;
    if (plmax) plmax.textContent = '/' + max;
    if (bar && max > 0) {
        bar.style.width = Math.round((cur / max) * 100) + '%';
    }
}

function updateAuditLog(logs) {
    const tbody = document.getElementById('audit-tbody');
    if (!tbody) return;
    if (!logs.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-muted" style="padding:14px">Brak wpisów</td></tr>';
        return;
    }
    tbody.innerHTML = logs.map(l => `
        <tr>
          <td class="text-muted fs-xs text-mono">${escHtml(l.created_at)}</td>
          <td class="text-accent">${escHtml(l.username || '—')}</td>
          <td>${escHtml(l.server_name || '—')}</td>
          <td class="fw-bold">${escHtml(l.action)}</td>
          <td class="text-muted fs-xs text-mono">${escHtml(l.ip || '—')}</td>
        </tr>
    `).join('');
}

// ── Server Detail ──────────────────────────────────────────
function startServerDetail(serverId) {
    refreshServerDetail(serverId);
    setInterval(() => refreshServerDetail(serverId), 10000);
    refreshZmq(serverId);
    setInterval(() => refreshZmq(serverId), 5000);
}

function refreshServerDetail(serverId) {
    fetch('/api/status/' + serverId)
        .then(r => r.json())
        .then(data => {
            if (!data.ok) return;
            const s    = data.data;
            const info = s.info || {};
            const running = s.running;

            const badge = document.getElementById('srv-status-badge');
            if (badge) {
                badge.className = running ? 'badge-online' : 'badge-offline';
                badge.textContent = running ? '● ONLINE' : '○ OFFLINE';
            }
            setTxt('srv-map',     info.map      || '—');
            setTxt('srv-gt',      info.gametype  || '—');
            setTxt('srv-players', (info.players_cur ?? 0) + ' / ' + (info.players_max ?? 0));

            updatePlayerTable(s.players || []);
        })
        .catch(() => {});
}

function updatePlayerTable(players) {
    const tbody = document.getElementById('player-tbody');
    const count = document.getElementById('players-count');
    if (!tbody) return;
    if (count) count.textContent = players.length + ' online';
    if (!players.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-muted" style="padding:14px">Brak graczy</td></tr>';
        return;
    }
    tbody.innerHTML = players.map((p, i) => `
        <tr>
          <td class="text-muted fs-xs">${i + 1}</td>
          <td class="fw-bold">${escHtml(p.name)}</td>
          <td class="text-gold">${p.score}</td>
          <td class="text-mono fs-xs">${p.ping}ms</td>
        </tr>
    `).join('');
}

// ── ZMQ Stats Feed ─────────────────────────────────────────
const zmqSeenIds = new Set();

function refreshZmq(serverId) {
    fetch('/api/zmq/stats/' + serverId + '?limit=30')
        .then(r => r.json())
        .then(data => {
            if (!data.ok || !data.events) return;
            const feed = document.getElementById('zmq-feed');
            if (!feed) return;

            const newEvents = data.events.filter(e => !zmqSeenIds.has(e.id || e.time + e.type));
            if (!newEvents.length) return;

            newEvents.forEach(e => {
                zmqSeenIds.add(e.id || e.time + e.type);
                const div = document.createElement('div');
                const isFrag = e.type === 'PLAYER_KILL' || e.type === 'PLAYER_DEATH';
                div.className = 'zmq-event' + (isFrag ? ' zmq-event-frag' : '');
                div.innerHTML = `
                    <span class="zmq-event-time">${escHtml(formatTime(e.time))}</span>
                    <span class="zmq-event-type">${escHtml(e.type || '?')}</span>
                    <span class="zmq-event-body">${escHtml(formatZmqBody(e))}</span>
                `;
                feed.appendChild(div);
            });

            // Limit do 100 wpisów w feedzie
            while (feed.children.length > 100) {
                feed.removeChild(feed.firstChild);
            }
            feed.scrollTop = feed.scrollHeight;
        })
        .catch(() => {});
}

function formatZmqBody(e) {
    if (e.type === 'PLAYER_KILL') {
        return (e.killer_name || '?') + ' → ' + (e.victim_name || '?') + ' [' + (e.mod || '') + ']';
    }
    if (e.type === 'PLAYER_CONNECT') return 'Połączono: ' + (e.player_name || '?');
    if (e.type === 'PLAYER_DISCONNECT') return 'Rozłączono: ' + (e.player_name || '?');
    if (e.type === 'MATCH_STARTED') return 'Mecz rozpoczęty: ' + (e.map || '') + ' ' + (e.factory || '');
    if (e.type === 'MATCH_REPORT') return 'Koniec meczu. Wynik: ' + (e.score_red || 0) + ' — ' + (e.score_blue || 0);
    return JSON.stringify(e.data || {});
}

function formatTime(ts) {
    if (!ts) return '--:--:--';
    const d = new Date(typeof ts === 'number' ? ts * 1000 : ts);
    return d.toLocaleTimeString('pl-PL', {hour12: false});
}

// ── Server control from dashboard ──────────────────────────
function controlServer(serverId, action) {
    if (!confirm('Wykonać akcję "' + action + '" na serwerze #' + serverId + '?')) return;
    fetch('/api/control', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({server_id: serverId, action: action})
    })
    .then(r => r.json())
    .then(d => alert(d.message))
    .catch(() => alert('Błąd połączenia z API'));
}

// ── Helpers ────────────────────────────────────────────────
function escHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function setTxt(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}
