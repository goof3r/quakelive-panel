import os
import secrets
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session
)
import auth
import database

main_bp = Blueprint('main', __name__)


def _check_setup():
    if auth.needs_setup():
        return redirect(url_for('main.setup'))
    return None


@main_bp.route('/')
def index():
    redir = _check_setup()
    if redir:
        return redir
    if session.get('user_id'):
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login_page'))


@main_bp.route('/login', methods=['GET', 'POST'])
def login_page():
    redir = _check_setup()
    if redir:
        return redir
    if session.get('user_id'):
        return redirect(url_for('main.dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if auth.login(username, password):
            auth.audit(0, 'login', f'Login z {request.remote_addr}')
            return redirect(url_for('main.dashboard'))
        error = 'Nieprawidłowy login lub hasło.'

    return render_template('login.html', error=error)


@main_bp.route('/logout')
def logout():
    if session.get('user_id'):
        auth.audit(0, 'logout', '')
    auth.logout()
    return redirect(url_for('main.login_page'))


@main_bp.route('/dashboard')
@auth.require_login
def dashboard():
    rows = database.query(
        '''SELECT id, name, host, game_port, screen_name, sort_order
           FROM servers WHERE enabled=1 ORDER BY sort_order, id'''
    )
    return render_template('dashboard.html',
                           servers=rows,
                           user=auth.current_user())


@main_bp.route('/server/<int:server_id>')
@auth.require_login
def server_detail(server_id):
    server = database.fetchone(
        'SELECT * FROM servers WHERE id=? AND enabled=1', (server_id,)
    )
    if not server:
        return 'Serwer nie znaleziony', 404
    return render_template('server.html',
                           server=server,
                           user=auth.current_user())


# ── Setup wizard ──────────────────────────────────────────────────────────────

@main_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if not auth.needs_setup():
        return redirect(url_for('main.login_page'))

    step   = int(request.args.get('step', 1))
    errors = []
    info   = []

    if request.method == 'POST':
        action = request.form.get('action', '')

        # Krok 1: Zapis konfiguracji
        if action == 'save_config':
            ssh_host    = request.form.get('ssh_host', '').strip()
            ssh_port    = request.form.get('ssh_port', '22').strip()
            ssh_user    = request.form.get('ssh_user', '').strip()
            ssh_key     = request.form.get('ssh_key', '').strip()
            qlds_dir    = request.form.get('qlds_dir', '/home/qladmin/qlds').strip()
            bridge_url  = request.form.get('bridge_url', 'http://127.0.0.1:8765').strip()
            bridge_token = request.form.get('bridge_token', '').strip()
            panel_title = request.form.get('panel_title', 'QL Server Panel').strip()
            port        = request.form.get('port', '9999').strip()

            if not ssh_host or not ssh_user or not ssh_key:
                errors.append('Uzupełnij dane SSH (host, user, klucz).')
            else:
                secret = secrets.token_hex(32)
                cfg_content = f'''# config.py — wygenerowany przez kreator instalacji
SSH_HOST    = {ssh_host!r}
SSH_PORT    = {int(ssh_port)}
SSH_USER    = {ssh_user!r}
SSH_KEY     = {ssh_key!r}
QLDS_DIR    = {qlds_dir!r}
SSH_TIMEOUT = 10

BRIDGE_URL    = {bridge_url!r}
BRIDGE_TOKEN  = {bridge_token!r}
BRIDGE_TIMEOUT = 5

SESSION_SECRET = {secret!r}
PANEL_TITLE    = {panel_title!r}
PORT           = {int(port)}
HOST           = '0.0.0.0'
DEBUG          = False

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_TIME = 300
'''
                cfg_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'config.py'
                )
                try:
                    with open(cfg_path, 'w') as f:
                        f.write(cfg_content)
                    return redirect(url_for('main.setup', step=2))
                except OSError as e:
                    errors.append(f'Nie można zapisać config.py: {e}')

        # Krok 2: Tworzenie konta admina
        elif action == 'create_admin':
            admin_user  = request.form.get('admin_user', 'admin').strip()
            admin_pass  = request.form.get('admin_pass', '')
            admin_pass2 = request.form.get('admin_pass2', '')

            if len(admin_user) < 3:
                errors.append('Login min. 3 znaki.')
            elif len(admin_pass) < 8:
                errors.append('Hasło min. 8 znaków.')
            elif admin_pass != admin_pass2:
                errors.append('Hasła nie są identyczne.')
            else:
                database.init_db()
                if auth.create_user(admin_user, admin_pass, 'admin'):
                    return redirect(url_for('main.setup', step=3))
                errors.append('Nie udało się utworzyć konta (username już zajęty?).')

        # Krok 3: Dodanie serwera QL
        elif action == 'add_server':
            game_port = int(request.form.get('game_port', 27960))
            database.execute(
                '''INSERT INTO servers
                   (name, host, game_port, zmq_stats_port, zmq_rcon_port,
                    screen_name, start_script, rcon_password, stats_password, sort_order)
                   VALUES (?,?,?,?,?,?,?,?,?,1)''',
                (
                    request.form.get('srv_name', 'QL Server'),
                    request.form.get('srv_host', '127.0.0.1'),
                    game_port,
                    int(request.form.get('zmq_stats', game_port)),
                    int(request.form.get('zmq_rcon',  game_port + 1000)),
                    request.form.get('screen_name', ''),
                    request.form.get('start_script', ''),
                    request.form.get('rcon_pass', ''),
                    request.form.get('stats_pass', ''),
                )
            )
            info.append('Serwer dodany.')

        elif action == 'finish':
            return redirect(url_for('main.login_page'))

    return render_template('setup.html', step=step, errors=errors, info=info)
