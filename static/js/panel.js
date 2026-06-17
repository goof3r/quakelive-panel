/* ============================================================
   QL Server Panel — qlip-style frontend
   ============================================================ */

// ── HEADER STATUS (dot + ts + countdown) ─────────────────────
let _cdInt   = null;
let _cdLeft  = 0;
let _refreshDelay = 15;
let _bar     = null;

function setHdrDot(state) {
    const el = document.getElementById('hdr-dot');
    if (el) el.className = 'dot ' + state;
}
function setHdrStatus(s) {
    const el = document.getElementById('hdr-status');
    if (el) el.textContent = s;
}
function setHdrTs(s) {
    const el = document.getElementById('hdr-ts');
    if (el) el.textContent = s;
}
function startHdrCountdown(seconds) {
    _refreshDelay = seconds;
    _cdLeft       = seconds;
    clearInterval(_cdInt);
    if (!_bar) _bar = document.getElementById('bar');
    const cdEl = document.getElementById('hdr-cd');
    _cdInt = setInterval(() => {
        _cdLeft--;
        if (cdEl) cdEl.textContent = _cdLeft;
        if (_bar) _bar.style.transform = `scaleX(${_cdLeft / _refreshDelay})`;
        if (_cdLeft <= 0) clearInterval(_cdInt);
    }, 1000);
}

// ── DASHBOARD ────────────────────────────────────────────────
function startDashboard(servers, isAdmin) {
    dashRefresh(servers, isAdmin);
    setInterval(() => dashRefresh(servers, isAdmin), 15000);
}

async function dashRefresh(servers, isAdmin) {
    setHdrDot('busy');
    setHdrStatus('querying...');
    try {
        const r = await fetch('/api/status');
        const d = await r.json();
        if (!d.ok) throw new Error('api');

        const merged = servers.map(s => {
            const st = d.servers[s.id] || {running: false, info: {}, players: []};
            return Object.assign({}, s, {
                running: !!st.running,
                info:    st.info || {},
                players: st.players || [],
                error:   st.error || null,
            });
        });

        renderDashStats(merged);
        renderDashCards(merged, isAdmin);
        setHdrDot('live');
        setHdrStatus('live');
        setHdrTs(new Date().toLocaleTimeString('pl-PL', {hour12: false}));
        startHdrCountdown(15);
    } catch (e) {
        setHdrDot('error');
        setHdrStatus('error');
    }
}

function renderDashStats(servers) {
    const el = document.getElementById('stats');
    if (!el) return;
    const on  = servers.filter(s => s.running).length;
    const tot = servers.length;
    const pl  = servers.reduce((a, s) =>
        a + (s.info?.players_cur ?? s.players?.length ?? 0), 0);
    const mx  = servers.reduce((a, s) => a + (s.info?.players_max ?? 0), 0);
    const act = servers.filter(s => (s.info?.players_cur ?? s.players?.length ?? 0) > 0).length;
    el.innerHTML =
        `<span>Online: <strong>${on}</strong>/${tot}</span>
         <span>Players: <strong>${pl}</strong>/${mx}</span>
         <span>Active: <strong>${act}</strong></span>`;
}

function renderDashCards(servers, isAdmin) {
    const root = document.getElementById('sections');
    if (!root) return;
    if (!servers.length) {
        root.innerHTML = `<div class="loading">Brak skonfigurowanych serwerów. Dodaj w panelu admina.</div>`;
        return;
    }
    const cards = servers.map(s => renderDashCard(s, isAdmin)).join('');
    root.innerHTML = `<div class="section">
        <div class="section-label">Servers</div>
        <div class="grid">${cards}</div>
    </div>`;
}

function renderDashCard(s, isAdmin) {
    const addr = `${s.host}:${s.game_port}`;
    const ipEl = `<span class="ip-copy" onclick="copyIp(this,'${escAttr(addr)}')">${escHtml(addr)}</span>`;
    const detailUrl = '/server/' + s.id;

    if (!s.running) {
        return `<div class="card dead">
            <div class="ch">
                <div style="min-width:0">
                    <div class="sname">${escHtml(s.name)}</div>
                    ${ipEl}
                </div>
            </div>
            <div class="badges"><span class="badge off">offline</span></div>
            ${renderCardActions(s, isAdmin, detailUrl, false)}
        </div>`;
    }

    const info  = s.info || {};
    const cur   = info.players_cur ?? s.players.length;
    const max   = info.players_max ?? 0;
    const ratio = max > 0 ? cur / max : 0;
    const fc    = barColor(ratio);

    return `<div class="card alive">
        <div class="ch">
            <div style="min-width:0">
                <div class="sname">${escHtml(s.name)}</div>
                ${ipEl}
            </div>
            <div class="pcount ${cur > 0 ? 'has' : ''}">
                ${cur}<span class="pmax">/${max}</span>
            </div>
        </div>
        <div class="badges">
            <span class="badge gt">${escHtml(info.gametype || '?')}</span>
            <span class="badge map">${escHtml(info.map || '?')}</span>
        </div>
        <div class="fbar-wrap">
            <div class="fbar"><div class="fbar-fill" style="width:${Math.round(ratio*100)}%;background:${fc}"></div></div>
        </div>
        ${renderPlayerList(s.players)}
        ${renderCardActions(s, isAdmin, detailUrl, true)}
    </div>`;
}

function renderPlayerList(list) {
    if (!list?.length) return '';
    const rows = list.map(p =>
        `<div class="prow">
            <span class="pn">${escHtml(p.name || '?')}</span>
            <span class="ps">${p.score ?? 0}</span>
            <span class="pt">${p.ping ?? 0}</span>
        </div>`).join('');
    return `<div class="plist">
        <div class="plist-hdr"><span>Player</span><span>Score</span><span>Ping</span></div>
        ${rows}
    </div>`;
}

function renderCardActions(s, isAdmin, detailUrl, isRunning) {
    const detailBtn = `<a class="btn-line" href="${detailUrl}">Szczegóły</a>`;
    if (!isAdmin) return `<div class="card-actions">${detailBtn}</div>`;
    return `<div class="card-actions">
        ${detailBtn}
        <button class="btn-line start" onclick="controlServer(${s.id},'start')">Start</button>
        <button class="btn-line warn"  onclick="controlServer(${s.id},'restart')">Restart</button>
        <button class="btn-line stop"  onclick="controlServer(${s.id},'stop')">Stop</button>
    </div>`;
}

function barColor(r) {
    if (r === 0)  return 'var(--muted)';
    if (r < 0.4)  return 'var(--green)';
    if (r < 0.75) return 'var(--accent)';
    return 'var(--red)';
}

function copyIp(el, text) {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(() => {
        const orig = el.textContent;
        el.textContent = 'copied!';
        el.classList.add('copied');
        setTimeout(() => { el.textContent = orig; el.classList.remove('copied'); }, 1200);
    });
}

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

// ── SERVER DETAIL ────────────────────────────────────────────
function startServerDetail(serverId) {
    refreshServerDetail(serverId);
    setInterval(() => refreshServerDetail(serverId), 10000);
    refreshZmq(serverId);
    setInterval(() => refreshZmq(serverId), 5000);
}

function refreshServerDetail(serverId) {
    setHdrDot('busy'); setHdrStatus('querying...');
    fetch('/api/status/' + serverId)
        .then(r => r.json())
        .then(data => {
            if (!data.ok) { setHdrDot('error'); setHdrStatus('error'); return; }
            const s    = data.data;
            const info = s.info || {};
            const running = s.running;

            const badge = document.getElementById('srv-status-badge');
            if (badge) {
                badge.className = 'badge ' + (running ? 'on' : 'off');
                badge.textContent = running ? 'online' : 'offline';
            }
            const stateDot = document.getElementById('srv-dot');
            const stateTxt = document.getElementById('srv-state');
            if (stateDot) stateDot.className = 'dot ' + (running ? 'live' : 'off');
            if (stateTxt) stateTxt.textContent = running ? 'online' : 'offline';

            setTxt('srv-map', info.map || '—');
            setTxt('srv-gt',  info.gametype || '—');
            setTxt('srv-players', (info.players_cur ?? 0) + ' / ' + (info.players_max ?? 0));

            updatePlayerTable(s.players || []);
            setHdrDot('live'); setHdrStatus('live');
            setHdrTs(new Date().toLocaleTimeString('pl-PL', {hour12: false}));
            startHdrCountdown(10);
        })
        .catch(() => { setHdrDot('error'); setHdrStatus('error'); });
}

function updatePlayerTable(players) {
    const tbody = document.getElementById('player-tbody');
    const count = document.getElementById('players-count');
    if (!tbody) return;
    if (count) count.textContent = players.length + ' online';
    if (!players.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-muted text-center" style="padding:18px">Brak graczy</td></tr>';
        return;
    }
    tbody.innerHTML = players.map((p, i) => `
        <tr>
            <td class="mono">${i + 1}</td>
            <td><strong>${escHtml(p.name)}</strong></td>
            <td style="text-align:right" class="text-accent">${p.score ?? 0}</td>
            <td style="text-align:right" class="mono">${p.ping ?? 0}ms</td>
        </tr>
    `).join('');
}

// ── ZMQ FEED ─────────────────────────────────────────────────
const zmqSeenIds = new Set();

function refreshZmq(serverId) {
    fetch('/api/zmq/stats/' + serverId + '?limit=30')
        .then(r => r.json())
        .then(data => {
            if (!data.ok || !data.events) return;
            const feed = document.getElementById('zmq-feed');
            if (!feed) return;

            const newEvents = data.events.filter(e =>
                !zmqSeenIds.has(e.id || (e.time + ':' + e.type)));
            if (!newEvents.length) return;

            newEvents.forEach(e => {
                zmqSeenIds.add(e.id || (e.time + ':' + e.type));
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

            while (feed.children.length > 100) feed.removeChild(feed.firstChild);
            feed.scrollTop = feed.scrollHeight;
        })
        .catch(() => {});
}

function formatZmqBody(e) {
    if (e.type === 'PLAYER_KILL')        return (e.killer_name || '?') + ' → ' + (e.victim_name || '?') + ' [' + (e.mod || '') + ']';
    if (e.type === 'PLAYER_CONNECT')     return 'Połączono: ' + (e.player_name || '?');
    if (e.type === 'PLAYER_DISCONNECT')  return 'Rozłączono: ' + (e.player_name || '?');
    if (e.type === 'MATCH_STARTED')      return 'Mecz: ' + (e.map || '') + ' ' + (e.factory || '');
    if (e.type === 'MATCH_REPORT')       return 'Koniec. ' + (e.score_red || 0) + ' — ' + (e.score_blue || 0);
    return JSON.stringify(e.data || {});
}

function formatTime(ts) {
    if (!ts) return '--:--:--';
    const d = new Date(typeof ts === 'number' ? ts * 1000 : ts);
    return d.toLocaleTimeString('pl-PL', {hour12: false});
}

// ── ADMIN: PLAYERS ───────────────────────────────────────────
function startPlayersAdmin(servers) {
    refreshPlayersAdmin(servers);
    setInterval(() => refreshPlayersAdmin(servers), 10000);
}

async function refreshPlayersAdmin(servers) {
    const dot = document.getElementById('pl-dot');
    const st  = document.getElementById('pl-state');
    if (dot) dot.className = 'dot busy';
    if (st)  st.textContent = 'querying...';

    try {
        const r = await fetch('/api/status');
        const d = await r.json();
        if (!d.ok) throw new Error('api');

        const root = document.getElementById('players-by-server');
        if (!root) return;

        const sections = servers.map(s => {
            const st  = d.servers[s.id];
            const run = st && st.running;
            const players = (st && st.players) || [];
            const info = (st && st.info) || {};
            return renderPlayersSection(s, run, players, info);
        }).join('');

        root.innerHTML = sections || `<div class="loading">Brak serwerów.</div>`;
        if (dot) dot.className = 'dot live';
        if (st)  st.textContent = 'live';
    } catch (e) {
        if (dot) dot.className = 'dot error';
        if (st)  st.textContent = 'error';
    }
}

function renderPlayersSection(srv, running, players, info) {
    const header = `<div class="panel-head">
        <span class="panel-title">${escHtml(srv.name)} <span class="text-muted text-mono" style="font-weight:normal;letter-spacing:.5px;text-transform:none">${escHtml(srv.host)}:${srv.game_port}</span></span>
        <span class="text-mono ${running ? 'text-success' : 'text-danger'}">
            ${running ? '● online' : '○ offline'}
            ${running ? ' · ' + escHtml(info.gametype || '?') + ' · ' + escHtml(info.map || '?') : ''}
        </span>
    </div>`;

    if (!running) {
        return `<div class="panel">${header}<div class="panel-body"><div class="text-muted text-mono">Serwer offline — brak danych o graczach.</div></div></div>`;
    }
    if (!players.length) {
        return `<div class="panel">${header}<div class="panel-body"><div class="text-muted text-mono">Brak graczy na serwerze.</div></div></div>`;
    }

    const rows = players.map(p => {
        const nameAttr = escAttr(p.name || '');
        const btn = (cls, act, lbl) =>
            `<button class="btn btn-sm ${cls}" data-sid="${srv.id}" data-pid="${p.id ?? 0}" data-pname="${nameAttr}" data-act="${act}" onclick="playerActionBtn(this)">${lbl}</button>`;
        return `
        <tr>
            <td class="mono">${p.id ?? '?'}</td>
            <td><strong>${escHtml(p.name)}</strong></td>
            <td style="text-align:right" class="text-accent">${p.score ?? 0}</td>
            <td style="text-align:right" class="mono">${p.ping ?? 0}ms</td>
            <td>
                <div class="btn-group">
                    ${btn('btn-warning',   'mute',    'Mute')}
                    ${btn('btn-secondary', 'unmute',  'Unmute')}
                    ${btn('btn-danger',    'kick',    'Kick')}
                    ${btn('btn-danger',    'kickban', 'Ban')}
                </div>
            </td>
        </tr>`;
    }).join('');

    return `<div class="panel">${header}
        <div class="panel-body tight">
            <table class="tbl">
                <thead><tr><th>ID</th><th>Nick</th><th style="text-align:right">Score</th><th style="text-align:right">Ping</th><th>Akcje</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    </div>`;
}

function playerActionBtn(el) {
    playerAction(
        parseInt(el.dataset.sid, 10),
        parseInt(el.dataset.pid, 10),
        el.dataset.pname || '',
        el.dataset.act || ''
    );
}

function playerAction(serverId, pid, pname, action) {
    const labels = {kick: 'wyrzucić', kickban: 'zbanować', mute: 'wyciszyć', unmute: 'odciszyć', tempban: 'tempbanować'};
    if (!confirm(`Czy ${labels[action] || action} gracza ${pname} (id=${pid})?`)) return;
    fetch('/api/admin/player_action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({server_id: serverId, pid: pid, pname: pname, action: action})
    })
        .then(r => r.json())
        .then(d => alert((d.ok ? '[OK] ' : '[BŁĄD] ') + (d.cmd || '') + '\n' + (d.response || d.message || '')))
        .catch(() => alert('Błąd połączenia z API'));
}

// ── ADMIN: MONITORING ────────────────────────────────────────
let _monLogTimer = null;

function startMonitoring() {
    refreshMonitoring();
    setInterval(refreshMonitoring, 5000);
    reloadLog();
    _monLogTimer = setInterval(() => {
        if (document.getElementById('log-auto')?.checked) reloadLog();
    }, 5000);
}

async function refreshMonitoring() {
    const dot = document.getElementById('mon-dot');
    const st  = document.getElementById('mon-state');
    if (dot) dot.className = 'dot busy';
    if (st)  st.textContent = 'querying...';
    try {
        const r = await fetch('/api/admin/system_stats');
        const d = await r.json();
        if (!d.ok) throw new Error('api');
        renderSysTiles(d.system || {});
        renderSvcTable(d.services || []);
        if (dot) dot.className = 'dot live';
        if (st)  st.textContent = 'live';
    } catch (e) {
        if (dot) dot.className = 'dot error';
        if (st)  st.textContent = 'error';
    }
}

function renderSysTiles(s) {
    if (!s || !s.ok) {
        setTxt('sys-load', 'n/a');
        setTxt('sys-mem',  'n/a');
        setTxt('sys-disk', 'n/a');
        setTxt('sys-up',   'n/a');
        return;
    }
    setTxt('sys-load',
        (s.load1 ?? 0).toFixed(2) + ' / ' +
        (s.load5 ?? 0).toFixed(2) + ' / ' +
        (s.load15 ?? 0).toFixed(2));

    const memPct = s.mem_total_mib > 0 ? Math.round(s.mem_used_mib / s.mem_total_mib * 100) : 0;
    setTxt('sys-mem',  `${(s.mem_used_mib/1024).toFixed(1)} / ${(s.mem_total_mib/1024).toFixed(1)} GiB (${memPct}%)`);
    const memBar = document.getElementById('sys-mem-bar');
    if (memBar) {
        memBar.style.width = memPct + '%';
        memBar.className = 'meter-fill' + (memPct > 90 ? ' crit' : memPct > 70 ? ' warn' : '');
    }

    setTxt('sys-disk', `${(s.disk_used_mib/1024).toFixed(1)} / ${(s.disk_total_mib/1024).toFixed(1)} GiB (${s.disk_pct || 0}%)`);
    const diskBar = document.getElementById('sys-disk-bar');
    if (diskBar) {
        diskBar.style.width = (s.disk_pct || 0) + '%';
        diskBar.className = 'meter-fill' + (s.disk_pct > 90 ? ' crit' : s.disk_pct > 70 ? ' warn' : '');
    }

    setTxt('sys-up', fmtUptime(s.uptime_sec || 0));
}

function fmtUptime(sec) {
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}

function renderSvcTable(services) {
    const tbody = document.getElementById('svc-tbody');
    const count = document.getElementById('svc-count');
    if (!tbody) return;
    if (count) count.textContent = services.length + ' serwerów';

    if (!services.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-muted text-center" style="padding:18px">Brak serwerów</td></tr>';
        return;
    }

    tbody.innerHTML = services.map(s => {
        const active = s.status === 'active';
        const stCls  = active ? 'b-on' : (s.status === 'unknown' ? 'text-muted' : 'b-off');
        const stLbl  = active ? '● active' : ('○ ' + (s.status || 'unknown'));
        return `<tr>
            <td><strong>${escHtml(s.name)}</strong></td>
            <td class="mono">${escHtml(s.host)}:${s.port}</td>
            <td class="mono">${escHtml(s.screen_name || '—')}</td>
            <td><span class="${stCls}">${stLbl}</span></td>
            <td>
                <div class="btn-group">
                    <button class="btn btn-sm btn-success" onclick="controlServer(${s.id},'start')">Start</button>
                    <button class="btn btn-sm btn-warning" onclick="controlServer(${s.id},'restart')">Restart</button>
                    <button class="btn btn-sm btn-danger"  onclick="controlServer(${s.id},'stop')">Stop</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

function reloadLog() {
    const srvEl   = document.getElementById('log-srv');
    const linesEl = document.getElementById('log-lines');
    const box     = document.getElementById('logbox');
    if (!srvEl || !box) return;
    const sid   = parseInt(srvEl.value, 10);
    const lines = parseInt(linesEl?.value || '100', 10);
    if (!sid) { box.textContent = 'Brak serwera.'; return; }

    fetch(`/api/admin/server_log/${sid}?lines=${lines}`)
        .then(r => r.json())
        .then(d => {
            if (!d.ok) { box.textContent = '[BŁĄD] ' + (d.message || 'brak danych'); return; }
            box.textContent = d.log || '(pusty log)';
            box.scrollTop = box.scrollHeight;
        })
        .catch(() => { box.textContent = '[BŁĄD] połączenia z API'; });
}

// ── HELPERS ──────────────────────────────────────────────────
function escHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function escAttr(s) {
    return escHtml(s).replace(/'/g, '&#39;');
}

function setTxt(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}
