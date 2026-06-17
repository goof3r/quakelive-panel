from flask import Blueprint, render_template, request, redirect, url_for, flash
import auth
import database

admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
@auth.require_admin
def before():
    pass


@admin_bp.route('/')
def index():
    srv_count = database.fetchone('SELECT COUNT(*) as c FROM servers WHERE enabled=1')['c']
    usr_count = database.fetchone('SELECT COUNT(*) as c FROM users')['c']
    log_count = database.fetchone('SELECT COUNT(*) as c FROM audit_log')['c']
    logs = database.query(
        '''SELECT a.*, u.username, s.name as server_name
           FROM audit_log a
           LEFT JOIN users u ON a.user_id = u.id
           LEFT JOIN servers s ON a.server_id = s.id
           ORDER BY a.created_at DESC LIMIT 20'''
    )
    return render_template('admin/index.html',
                           user=auth.current_user(),
                           srv_count=srv_count,
                           usr_count=usr_count,
                           log_count=log_count,
                           logs=logs)


@admin_bp.route('/users', methods=['GET', 'POST'])
def users():
    message  = None
    msg_type = 'info'
    cur_user = auth.current_user()

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'add':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            role     = request.form.get('role', 'viewer')
            if role not in ('admin', 'viewer'):
                role = 'viewer'
            if len(username) < 3 or len(password) < 6:
                message, msg_type = 'Login min. 3 znaki, hasło min. 6 znaków.', 'error'
            elif auth.create_user(username, password, role):
                auth.audit(0, 'user_add', f'Dodano: {username} ({role})')
                message, msg_type = f'Użytkownik {username} dodany.', 'success'
            else:
                message, msg_type = 'Błąd: użytkownik już istnieje.', 'error'

        elif action == 'delete':
            del_id = int(request.form.get('user_id', 0))
            if del_id == cur_user['id']:
                message, msg_type = 'Nie możesz usunąć samego siebie.', 'error'
            else:
                u = database.fetchone('SELECT username FROM users WHERE id=?', (del_id,))
                if u:
                    database.execute('DELETE FROM users WHERE id=?', (del_id,))
                    auth.audit(0, 'user_delete', f"Usunięto: {u['username']}")
                    message, msg_type = f"Użytkownik {u['username']} usunięty.", 'success'

        elif action == 'change_password':
            edit_id  = int(request.form.get('user_id', 0))
            new_pass = request.form.get('new_password', '')
            if len(new_pass) < 6:
                message, msg_type = 'Hasło min. 6 znaków.', 'error'
            else:
                hashed = auth.hash_password(new_pass)
                database.execute('UPDATE users SET password_hash=? WHERE id=?', (hashed, edit_id))
                auth.audit(0, 'password_change', f'user_id={edit_id}')
                message, msg_type = 'Hasło zmienione.', 'success'

    users_list = database.query(
        'SELECT id, username, role, last_login, created_at FROM users ORDER BY id'
    )
    return render_template('admin/users.html',
                           user=cur_user,
                           users_list=users_list,
                           message=message,
                           msg_type=msg_type)


@admin_bp.route('/logs')
def logs():
    filter_user   = request.args.get('user', '').strip()
    filter_action = request.args.get('action', '').strip()
    filter_server = int(request.args.get('server', 0))
    page          = max(1, int(request.args.get('page', 1)))
    per_page      = 50
    offset        = (page - 1) * per_page

    where  = []
    params = []
    if filter_user:
        where.append('u.username LIKE ?')
        params.append(f'%{filter_user}%')
    if filter_action:
        where.append('a.action LIKE ?')
        params.append(f'%{filter_action}%')
    if filter_server:
        where.append('a.server_id = ?')
        params.append(filter_server)

    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    total = database.fetchone(
        f'SELECT COUNT(*) as c FROM audit_log a LEFT JOIN users u ON a.user_id=u.id {where_sql}',
        tuple(params)
    )['c']

    log_rows = database.query(
        f'''SELECT a.*, u.username, s.name as server_name
            FROM audit_log a
            LEFT JOIN users u ON a.user_id = u.id
            LEFT JOIN servers s ON a.server_id = s.id
            {where_sql}
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?''',
        tuple(params) + (per_page, offset)
    )

    servers = database.query('SELECT id, name FROM servers ORDER BY sort_order, id')
    pages   = max(1, (total + per_page - 1) // per_page)

    return render_template('admin/logs.html',
                           user=auth.current_user(),
                           logs=log_rows,
                           total=total,
                           page=page,
                           pages=pages,
                           servers=servers,
                           filter_user=filter_user,
                           filter_action=filter_action,
                           filter_server=filter_server)


@admin_bp.route('/servers', methods=['GET', 'POST'])
def servers():
    cur_user = auth.current_user()
    message  = None
    msg_type = 'info'

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'add':
            game_port = int(request.form.get('game_port', 27960))
            database.execute(
                '''INSERT INTO servers
                   (name, host, game_port, zmq_stats_port, zmq_rcon_port,
                    screen_name, start_script, rcon_password, stats_password,
                    bridge_port, enabled, sort_order)
                   VALUES (?,?,?,?,?,?,?,?,?,8765,1,?)''',
                (
                    request.form.get('name', '').strip(),
                    request.form.get('host', '').strip(),
                    game_port,
                    int(request.form.get('zmq_stats', game_port)),
                    int(request.form.get('zmq_rcon',  game_port + 1000)),
                    request.form.get('screen_name', '').strip(),
                    request.form.get('start_script', '').strip(),
                    request.form.get('rcon_pass', ''),
                    request.form.get('stats_pass', ''),
                    int(request.form.get('sort_order', 99)),
                )
            )
            auth.audit(0, 'server_add', request.form.get('name', ''))
            message, msg_type = 'Serwer dodany.', 'success'

        elif action == 'delete':
            sid = int(request.form.get('server_id', 0))
            srv = database.fetchone('SELECT name FROM servers WHERE id=?', (sid,))
            if srv:
                database.execute('DELETE FROM servers WHERE id=?', (sid,))
                auth.audit(sid, 'server_delete', srv['name'])
                message, msg_type = f"Serwer {srv['name']} usunięty.", 'success'

        elif action == 'toggle':
            sid = int(request.form.get('server_id', 0))
            database.execute(
                'UPDATE servers SET enabled = 1 - enabled WHERE id=?', (sid,)
            )
            auth.audit(sid, 'server_toggle', '')
            message, msg_type = 'Status serwera zmieniony.', 'success'

    srv_list = database.query('SELECT * FROM servers ORDER BY sort_order, id')
    return render_template('admin/servers.html',
                           user=cur_user,
                           servers=srv_list,
                           message=message,
                           msg_type=msg_type)


@admin_bp.route('/players')
def players():
    srv_list = database.query(
        '''SELECT id, name, host, game_port, screen_name
           FROM servers WHERE enabled=1 ORDER BY sort_order, id'''
    )
    return render_template('admin/players.html',
                           user=auth.current_user(),
                           servers=srv_list)


@admin_bp.route('/monitoring')
def monitoring():
    srv_list = database.query(
        '''SELECT id, name, host, game_port, screen_name
           FROM servers WHERE enabled=1 ORDER BY sort_order, id'''
    )
    return render_template('admin/monitoring.html',
                           user=auth.current_user(),
                           servers=srv_list)
