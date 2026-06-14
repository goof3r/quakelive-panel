import bcrypt
from functools import wraps
from flask import session, redirect, url_for, request, abort
import database


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def login(username: str, password: str) -> bool:
    # Prosta blokada w sesji
    fail_key  = f'fail_{username}'
    time_key  = f'fail_time_{username}'
    import time, config
    attempts  = session.get(fail_key, 0)
    last_fail = session.get(time_key, 0)

    if attempts >= config.MAX_LOGIN_ATTEMPTS:
        if (time.time() - last_fail) < config.LOGIN_LOCKOUT_TIME:
            return False
        session.pop(fail_key, None)
        session.pop(time_key, None)

    user = database.fetchone(
        'SELECT id, username, password_hash, role FROM users WHERE username = ?',
        (username,)
    )
    if not user or not check_password(password, user['password_hash']):
        session[fail_key]  = session.get(fail_key, 0) + 1
        session[time_key]  = time.time()
        return False

    session.clear()
    session['user_id']   = user['id']
    session['user_name'] = user['username']
    session['user_role'] = user['role']
    session.permanent    = True

    database.execute(
        "UPDATE users SET last_login = datetime('now') WHERE id = ?",
        (user['id'],)
    )
    return True


def logout() -> None:
    session.clear()


def current_user() -> dict:
    return {
        'id':   session.get('user_id', 0),
        'name': session.get('user_name', ''),
        'role': session.get('user_role', ''),
    }


def is_admin() -> bool:
    return session.get('user_role') == 'admin'


def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('main.login_page'))
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('main.login_page'))
        if session.get('user_role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


def audit(server_id: int, action: str, detail: str = '') -> None:
    database.execute(
        'INSERT INTO audit_log (user_id, server_id, action, detail, ip) VALUES (?,?,?,?,?)',
        (
            session.get('user_id'),
            server_id or None,
            action,
            detail,
            request.remote_addr or '',
        )
    )


def create_user(username: str, password: str, role: str = 'viewer') -> bool:
    try:
        database.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?,?,?)',
            (username, hash_password(password), role)
        )
        return True
    except Exception:
        return False


def needs_setup() -> bool:
    try:
        import config
        if 'ZMIEN_' in config.SESSION_SECRET:
            return True
        if database.fetchone('SELECT id FROM users LIMIT 1') is None:
            return True
        return False
    except (ImportError, Exception):
        return True
