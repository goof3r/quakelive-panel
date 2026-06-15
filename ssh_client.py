import paramiko
import re
import time

import config


def _connect() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=config.SSH_HOST,
        port=config.SSH_PORT,
        username=config.SSH_USER,
        key_filename=config.SSH_KEY,
        timeout=config.SSH_TIMEOUT,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def ssh_exec(cmd: str) -> str:
    client = _connect()
    try:
        _, stdout, _ = client.exec_command(cmd, timeout=15)
        return stdout.read().decode('utf-8', errors='replace')
    finally:
        client.close()


def test_connection() -> dict:
    try:
        out = ssh_exec('hostname && echo "SSH_OK"')
        if 'SSH_OK' in out:
            return {'ok': True, 'message': f'SSH OK. Host: {out.split()[0]}'}
        return {'ok': False, 'message': 'Nieoczekiwana odpowiedź SSH'}
    except Exception as e:
        return {'ok': False, 'message': f'SSH error: {e}'}


def is_service_active(service_name: str) -> bool:
    out = ssh_exec(f'systemctl is-active {service_name}.service 2>/dev/null || true')
    return out.strip() == 'active'


def _parse_status(raw: str) -> tuple[dict, list]:
    info    = {}
    players = []
    for line in raw.splitlines():
        line = line.strip()
        if m := re.match(r'^map:\s+(\S+)', line, re.I):
            info['map'] = m.group(1)
        elif m := re.match(r'^hostname:\s+(.+)', line, re.I):
            info['hostname'] = m.group(1).strip()
        elif m := re.match(r'^gametype:\s+(\S+)', line, re.I):
            info['gametype'] = m.group(1)
        elif m := re.match(r'^players:\s+(\d+)/(\d+)', line, re.I):
            info['players_cur'] = int(m.group(1))
            info['players_max'] = int(m.group(2))
        elif m := re.match(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+(.+)$', line):
            players.append({
                'score': int(m.group(1)),
                'ping':  int(m.group(2)),
                'id':    int(m.group(3)),
                'name':  m.group(4).strip(),
            })
    return info, players


def _zmq_rcon(server: dict, cmd: str) -> str:
    host     = server.get('host', '127.0.0.1')
    port     = server.get('zmq_rcon_port') or (server.get('game_port', 27960) + 1000)
    password = server.get('rcon_password', '')
    py_cmd = (
        "python3 -c \""
        "import zmq,json,sys;"
        "ctx=zmq.Context();"
        "s=ctx.socket(zmq.DEALER);"
        f"s.plain_username=b'rcon';"
        f"s.plain_password={password!r}.encode();"
        f"s.connect('tcp://{host}:{port}');"
        f"s.send_multipart([b'',json.dumps({{'cmd':{cmd!r}}}).encode()]);"
        "print(s.recv_multipart()[-1].decode() if s.poll(3000) else '(timeout)');"
        "s.close();ctx.term()"
        "\" 2>/dev/null"
    )
    try:
        return ssh_exec(py_cmd)
    except Exception:
        return ''


def get_server_status(server: dict) -> dict:
    service = server['screen_name']
    running = is_service_active(service)
    info, players = {}, []

    if running:
        raw = _zmq_rcon(server, 'status')
        if raw:
            info, players = _parse_status(raw)

    return {
        'running':     running,
        'screen_name': service,
        'info':        info,
        'players':     players,
    }


def start_server(server: dict) -> bool:
    service = server['screen_name']
    ssh_exec(f'systemctl start {service}.service 2>/dev/null || true')
    time.sleep(2)
    return is_service_active(service)


def stop_server(server: dict) -> bool:
    service = server['screen_name']
    ssh_exec(f'systemctl stop {service}.service 2>/dev/null || true')
    time.sleep(2)
    return not is_service_active(service)


def restart_server(server: dict) -> bool:
    service = server['screen_name']
    ssh_exec(f'systemctl restart {service}.service 2>/dev/null || true')
    time.sleep(3)
    return is_service_active(service)


def get_log(server: dict, lines: int = 50) -> str:
    service = server['screen_name']
    try:
        return ssh_exec(f'journalctl -u {service}.service -n {lines} --no-pager 2>/dev/null || true')
    except Exception:
        return ''
