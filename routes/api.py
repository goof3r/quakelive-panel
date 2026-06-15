from flask import Blueprint, request, jsonify, session
import auth
import database
import ssh_client
import zmq_client

api_bp = Blueprint('api', __name__)


@api_bp.before_request
def check_login():
    if not session.get('user_id'):
        return jsonify({'ok': False, 'message': 'Nieautoryzowany'}), 401


# ── Status serwerów ───────────────────────────────────────────────────────────

@api_bp.route('/status')
def all_status():
    servers = database.query(
        'SELECT * FROM servers WHERE enabled=1 ORDER BY sort_order, id'
    )
    result  = {}
    for srv in servers:
        try:
            result[srv['id']] = ssh_client.get_server_status(srv)
            result[srv['id']]['name'] = srv['name']
        except Exception as e:
            result[srv['id']] = {
                'running': False,
                'error':   str(e),
                'name':    srv['name'],
                'info':    {},
                'players': [],
            }

    logs = database.query(
        '''SELECT a.*, u.username, s.name as server_name
           FROM audit_log a
           LEFT JOIN users u ON a.user_id = u.id
           LEFT JOIN servers s ON a.server_id = s.id
           ORDER BY a.created_at DESC LIMIT 10'''
    )
    return jsonify({'ok': True, 'servers': result, 'logs': logs})


@api_bp.route('/status/<int:server_id>')
def single_status(server_id):
    server = database.fetchone(
        'SELECT * FROM servers WHERE id=? AND enabled=1', (server_id,)
    )
    if not server:
        return jsonify({'ok': False, 'message': 'Serwer nie znaleziony'}), 404
    try:
        data = ssh_client.get_server_status(server)
        return jsonify({'ok': True, 'data': data})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)}), 500


# ── Sterowanie serwerami ──────────────────────────────────────────────────────

@api_bp.route('/control', methods=['POST'])
def control():
    if session.get('user_role') != 'admin':
        return jsonify({'ok': False, 'message': 'Brak uprawnień admina'}), 403

    body      = request.get_json(force=True) or {}
    server_id = int(body.get('server_id', 0))
    action    = str(body.get('action', ''))

    if action not in ('start', 'stop', 'restart'):
        return jsonify({'ok': False, 'message': f'Nieznana akcja: {action}'}), 400

    server = database.fetchone(
        'SELECT * FROM servers WHERE id=? AND enabled=1', (server_id,)
    )
    if not server:
        return jsonify({'ok': False, 'message': 'Serwer nie znaleziony'}), 404

    try:
        if action == 'start':
            ok  = ssh_client.start_server(server)
            msg = 'Serwer uruchomiony.' if ok else 'Błąd uruchamiania.'
        elif action == 'stop':
            ok  = ssh_client.stop_server(server)
            msg = 'Serwer zatrzymany.' if ok else 'Błąd zatrzymywania.'
        else:
            ok  = ssh_client.restart_server(server)
            msg = 'Serwer zrestartowany.' if ok else 'Błąd restartu.'

        auth.audit(server_id, action, msg)
        return jsonify({'ok': ok, 'message': msg})
    except Exception as e:
        return jsonify({'ok': False, 'message': f'SSH error: {e}'}), 500


# ── ZMQ stats i rcon ─────────────────────────────────────────────────────────

@api_bp.route('/zmq/stats/<int:server_id>')
def zmq_stats(server_id):
    limit  = min(50, int(request.args.get('limit', 30)))
    events = zmq_client.get_stats(server_id, limit)
    return jsonify({'ok': True, 'events': events})


@api_bp.route('/debug/<int:server_id>')
def debug_server(server_id):
    if session.get('user_role') != 'admin':
        return jsonify({'ok': False, 'message': 'Tylko admin'}), 403
    server = database.fetchone('SELECT * FROM servers WHERE id=?', (server_id,))
    if not server:
        return jsonify({'ok': False, 'message': 'Brak serwera'}), 404
    out = {}
    try:
        out['ssh_test'] = ssh_client.test_connection()
    except Exception as e:
        out['ssh_test'] = {'ok': False, 'message': str(e)}
    try:
        out['systemctl_status'] = ssh_client.ssh_exec(
            f"systemctl is-active {server['screen_name']}.service 2>/dev/null || true"
        )
    except Exception as e:
        out['systemctl_status'] = f'ERROR: {e}'
    try:
        out['service_active'] = ssh_client.is_service_active(server['screen_name'])
    except Exception as e:
        out['service_active'] = f'ERROR: {e}'
    try:
        out['zmq_rcon_raw'] = ssh_client._zmq_rcon(server, 'status')
    except Exception as e:
        out['zmq_rcon_raw'] = f'ERROR: {e}'
    out['server_record'] = dict(server)
    return jsonify({'ok': True, 'debug': out})


@api_bp.route('/zmq/rcon', methods=['POST'])
def zmq_rcon():
    if session.get('user_role') != 'admin':
        return jsonify({'ok': False, 'message': 'Brak uprawnień admina'}), 403

    body      = request.get_json(force=True) or {}
    server_id = int(body.get('server_id', 0))
    cmd       = str(body.get('cmd', '')).strip()

    if not cmd:
        return jsonify({'ok': False, 'message': 'Brak komendy'}), 400

    auth.audit(server_id, 'rcon', cmd)
    response = zmq_client.send_rcon(server_id, cmd)
    return jsonify({'ok': True, 'response': response or '(brak odpowiedzi od bridge)'})
