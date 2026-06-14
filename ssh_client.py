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


def is_screen_running(screen_name: str) -> bool:
    out = ssh_exec(
        f'screen -ls 2>/dev/null | grep -c {screen_name!r} || true'
    )
    try:
        return int(out.strip().splitlines()[0]) > 0
    except (ValueError, IndexError):
        return False


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
    running = is_screen_running(server['screen_name'])
    info, players = {}, []

    if running:
        raw = _zmq_rcon(server, 'status')
        if raw:
            info, players = _parse_status(raw)

    return {
        'running':      running,
        'screen_name':  server.get('screen_name', ''),
        'info':         info,
        'players':      players,
    }


def start_server(server: dict) -> bool:
    script = f"{config.QLDS_DIR}/{server['start_script']}"
    screen = server['screen_name']
    cmd = (
        f"screen -dmS {screen} bash -c {script!r} && sleep 2"
    )
    ssh_exec(cmd)
    return is_screen_running(screen)


def stop_server(server: dict) -> bool:
    screen = server['screen_name']
    ssh_exec(f"screen -S {screen} -X stuff 'quit\\n' 2>/dev/null; sleep 2")
    return not is_screen_running(screen)


def restart_server(server: dict) -> bool:
    stop_server(server)
    time.sleep(2)
    return start_server(server)


def get_log(server: dict, lines: int = 50) -> str:
    log_file = f"{config.QLDS_DIR}/baseq3/{server['screen_name']}.log"
    try:
        return ssh_exec(f"tail -n {lines} {log_file!r} 2>/dev/null")
    except Exception:
        return ''
