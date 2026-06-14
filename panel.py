#!/usr/bin/env python3
"""
Quake Live Server Panel
Uruchomienie: python3 panel.py   (lub ./venv/bin/python panel.py)
Panel dostępny na: http://0.0.0.0:9999
"""

import sys
import os

# Sprawdź czy config.py istnieje; jeśli nie — uruchom panel i pokaż setup wizard
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.py')
if not os.path.exists(_CONFIG_PATH):
    # Utwórz minimalny config żeby Flask mógł wystartować (bez wrażliwych danych)
    import secrets
    _tmp_secret = secrets.token_hex(32)
    with open(_CONFIG_PATH, 'w') as _f:
        _f.write(f"""# Tymczasowy config — uzupełnij przez kreator /setup
SSH_HOST = 'ZMIEN_HOST'
SSH_PORT = 22
SSH_USER = 'ZMIEN_USER'
SSH_KEY  = '/home/user/.ssh/id_ed25519'
QLDS_DIR = '/home/qladmin/qlds'
SSH_TIMEOUT = 10
BRIDGE_URL    = 'http://127.0.0.1:8765'
BRIDGE_TOKEN  = 'ZMIEN_TOKEN'
BRIDGE_TIMEOUT = 5
SESSION_SECRET = {_tmp_secret!r}
PANEL_TITLE    = 'QL Server Panel'
PORT  = 9999
HOST  = '0.0.0.0'
DEBUG = False
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_TIME = 300
""")

import config
from flask import Flask
from routes.main  import main_bp
from routes.api   import api_bp
from routes.admin import admin_bp
from database import init_db

app = Flask(__name__)
app.secret_key      = config.SESSION_SECRET
app.config['config'] = config  # dostępne w szablonach jako config.*

# Udostępnij config w szablonach
@app.context_processor
def inject_config():
    return {'config': config}

app.register_blueprint(main_bp)
app.register_blueprint(api_bp,    url_prefix='/api')
app.register_blueprint(admin_bp,  url_prefix='/admin')


@app.errorhandler(403)
def forbidden(e):
    return '<h2 style="color:#ff6600;font-family:monospace">403 — Brak uprawnień</h2>', 403


@app.errorhandler(404)
def not_found(e):
    return '<h2 style="color:#ff6600;font-family:monospace">404 — Nie znaleziono</h2>', 404


if __name__ == '__main__':
    init_db()
    port  = getattr(config, 'PORT',  9999)
    host  = getattr(config, 'HOST',  '0.0.0.0')
    debug = getattr(config, 'DEBUG', False)

    print(f"\n  ╔══════════════════════════════════════╗")
    print(f"  ║  Quake Live Server Panel             ║")
    print(f"  ║  http://{host}:{port}              ║")
    print(f"  ╚══════════════════════════════════════╝\n")

    app.run(host=host, port=port, debug=debug, use_reloader=False)
