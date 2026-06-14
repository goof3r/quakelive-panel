#!/usr/bin/env python3
"""
Quake Live ZMQ Bridge
=====================
Subskrybuje ZMQ stats z serwerów QL i udostępnia REST API dla panelu PHP.

Uruchom na SERWERZE QL (lokalnie obok QLDS):
  python3 bridge.py

Domyślny port: 8765
Konfiguracja: bridge_config.json (tworzony przy pierwszym uruchomieniu)
"""

import json
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime
from functools import wraps
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    import zmq
except ImportError:
    sys.exit("Brak pyzmq. Zainstaluj: pip3 install pyzmq flask")

# ── Konfiguracja ──────────────────────────────────────────────────────────────

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'bridge_config.json')

DEFAULT_CONFIG = {
    "listen_host": "0.0.0.0",
    "listen_port": 8765,
    "bearer_token": "ZMIEN_TOKEN_BRIDGE",
    "max_events": 200,
    "servers": [
        {
            "id": 1,
            "name": "FT Server",
            "host": "127.0.0.1",
            "game_port": 27960,
            "zmq_stats_port": 27960,
            "zmq_rcon_port": 28960,
            "rcon_password": "zmien_rcon",
            "stats_password": "zmien_stats"
        }
    ]
}

def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"[!] Stworzono domyślny plik konfiguracyjny: {CONFIG_FILE}")
        print("[!] Uzupełnij dane serwerów i ZMIEŃ bearer_token!")
    with open(CONFIG_FILE) as f:
        return json.load(f)

CONFIG = load_config()
MAX_EVENTS = CONFIG.get('max_events', 200)
BEARER     = CONFIG.get('bearer_token', '')

# ── Bufor eventów (per serwer) ────────────────────────────────────────────────

events_lock = threading.Lock()
events_buf:  dict[int, deque] = {}
status_buf:  dict[int, dict]  = {}

for srv in CONFIG.get('servers', []):
    sid = srv['id']
    events_buf[sid] = deque(maxlen=MAX_EVENTS)
    status_buf[sid] = {}

# ── ZMQ subscriber threads ────────────────────────────────────────────────────

def zmq_stats_worker(server: dict):
    sid      = server['id']
    host     = server.get('host', '127.0.0.1')
    port     = server.get('zmq_stats_port', server.get('game_port', 27960))
    password = server.get('stats_password', '')

    addr = f"tcp://{host}:{port}"
    print(f"[ZMQ] Server {sid} ({server['name']}): subscribe {addr}")

    ctx = zmq.Context.instance()
    while True:
        sock = ctx.socket(zmq.SUB)
        try:
            if password:
                sock.plain_username = b'stats'
                sock.plain_password = password.encode()
            sock.connect(addr)
            sock.setsockopt(zmq.SUBSCRIBE, b'')
            sock.setsockopt(zmq.RCVTIMEO, 10000)

            while True:
                try:
                    raw = sock.recv()
                    process_stats_message(sid, raw)
                except zmq.Again:
                    pass
        except Exception as e:
            print(f"[ZMQ] Server {sid} error: {e}")
        finally:
            sock.close()
        time.sleep(5)

def process_stats_message(sid: int, raw: bytes):
    try:
        data = json.loads(raw.decode('utf-8', errors='replace'))
    except Exception:
        return

    event_type = data.get('TYPE', 'UNKNOWN')
    payload    = data.get('DATA', data)
    now        = datetime.now().isoformat()

    event = {
        'id':   f"{sid}-{now}-{event_type}",
        'time': now,
        'type': event_type,
    }

    # Wyciągnij kluczowe dane z eventów
    if event_type == 'PLAYER_KILL':
        event['killer_name'] = payload.get('KILLER', {}).get('NAME', '?')
        event['victim_name'] = payload.get('VICTIM', {}).get('NAME', '?')
        event['mod']         = payload.get('MOD', '')
    elif event_type in ('PLAYER_CONNECT', 'PLAYER_DISCONNECT'):
        event['player_name'] = payload.get('NAME', payload.get('STEAM_ID', '?'))
    elif event_type == 'MATCH_STARTED':
        event['map']     = payload.get('MAP', '')
        event['factory'] = payload.get('FACTORY', '')
        with events_lock:
            status_buf[sid]['map']     = event['map']
            status_buf[sid]['factory'] = event['factory']
            status_buf[sid]['players'] = []
    elif event_type == 'MATCH_REPORT':
        event['score_red']  = payload.get('TSCORE0', 0)
        event['score_blue'] = payload.get('TSCORE1', 0)
    elif event_type == 'PLAYER_STATS':
        pass

    event['data'] = payload if event_type not in ('PLAYER_KILL', 'PLAYER_CONNECT', 'PLAYER_DISCONNECT') else {}

    with events_lock:
        events_buf[sid].append(event)

# ── ZMQ Rcon ────────────────────────────────────────────────────────────────

def send_rcon(server: dict, cmd: str, timeout_ms: int = 4000) -> str:
    host     = server.get('host', '127.0.0.1')
    port     = server.get('zmq_rcon_port', server.get('game_port', 27960) + 1000)
    password = server.get('rcon_password', '')

    ctx  = zmq.Context.instance()
    sock = ctx.socket(zmq.DEALER)
    try:
        if password:
            sock.plain_username = b'rcon'
            sock.plain_password = password.encode()
        sock.connect(f"tcp://{host}:{port}")
        sock.setsockopt(zmq.SNDTIMEO, timeout_ms)
        sock.setsockopt(zmq.RCVTIMEO, timeout_ms)

        msg = json.dumps({'cmd': cmd})
        sock.send_multipart([b'', msg.encode()])

        if sock.poll(timeout_ms):
            parts = sock.recv_multipart()
            return parts[-1].decode('utf-8', errors='replace')
        return '(timeout)'
    except Exception as e:
        return f'(error: {e})'
    finally:
        sock.close()

# ── HTTP API ─────────────────────────────────────────────────────────────────

def get_server_by_id(sid: int) -> dict | None:
    for s in CONFIG.get('servers', []):
        if s['id'] == sid:
            return s
    return None

class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def check_auth(self) -> bool:
        auth = self.headers.get('Authorization', '')
        return auth == f'Bearer {BEARER}'

    def do_GET(self):
        if not self.check_auth():
            self.send_json(401, {'error': 'Unauthorized'})
            return

        path = self.path.split('?')[0].rstrip('/')

        if path.startswith('/stats/'):
            sid = int(path.split('/')[-1])
            with events_lock:
                evts = list(events_buf.get(sid, []))
            self.send_json(200, {'ok': True, 'events': list(reversed(evts[-50:]))})

        elif path.startswith('/status/'):
            sid = int(path.split('/')[-1])
            with events_lock:
                s = dict(status_buf.get(sid, {}))
            self.send_json(200, {'ok': True, 'data': s})

        elif path == '/health':
            self.send_json(200, {'ok': True, 'servers': len(CONFIG.get('servers', []))})

        else:
            self.send_json(404, {'error': 'Not Found'})

    def do_POST(self):
        if not self.check_auth():
            self.send_json(401, {'error': 'Unauthorized'})
            return

        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)

        try:
            data = json.loads(body)
        except Exception:
            self.send_json(400, {'error': 'Invalid JSON'})
            return

        path = self.path.rstrip('/')

        if path == '/rcon':
            sid = int(data.get('server_id', 0))
            cmd = str(data.get('cmd', '')).strip()
            srv = get_server_by_id(sid)
            if not srv or not cmd:
                self.send_json(400, {'error': 'Brak server_id lub cmd'})
                return
            resp = send_rcon(srv, cmd)
            self.send_json(200, {'ok': True, 'response': resp})
        else:
            self.send_json(404, {'error': 'Not Found'})

# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"[*] Quake Live ZMQ Bridge v1.0")
    print(f"[*] Konfiguracja: {CONFIG_FILE}")
    print(f"[*] Serwery: {len(CONFIG.get('servers', []))}")

    # Uruchom subscriber dla każdego serwera
    for srv in CONFIG.get('servers', []):
        t = threading.Thread(target=zmq_stats_worker, args=(srv,), daemon=True)
        t.start()

    # HTTP server
    host = CONFIG.get('listen_host', '0.0.0.0')
    port = CONFIG.get('listen_port', 8765)
    httpd = HTTPServer((host, port), BridgeHandler)
    print(f"[*] HTTP API: http://{host}:{port}")
    print(f"[*] Token: {BEARER[:4]}***")
    print("[*] Ctrl+C aby zatrzymać\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Zatrzymano.")
