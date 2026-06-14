import requests
import config


def _get(endpoint: str, params: dict | None = None) -> dict | None:
    try:
        url = f"{config.BRIDGE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
        r = requests.get(
            url,
            params=params,
            headers={'Authorization': f'Bearer {config.BRIDGE_TOKEN}'},
            timeout=config.BRIDGE_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _post(endpoint: str, body: dict) -> dict | None:
    try:
        url = f"{config.BRIDGE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
        r = requests.post(
            url,
            json=body,
            headers={'Authorization': f'Bearer {config.BRIDGE_TOKEN}'},
            timeout=config.BRIDGE_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def get_stats(server_id: int, limit: int = 30) -> list:
    data = _get(f'stats/{server_id}', {'limit': limit})
    return data.get('events', []) if data else []


def get_status(server_id: int) -> dict | None:
    data = _get(f'status/{server_id}')
    return data.get('data') if data else None


def send_rcon(server_id: int, cmd: str) -> str | None:
    data = _post('rcon', {'server_id': server_id, 'cmd': cmd})
    return data.get('response') if data else None


def test_bridge() -> dict:
    data = _get('health')
    if data and data.get('ok'):
        return {'ok': True, 'message': f"Bridge OK. Serwery: {data.get('servers', '?')}"}
    return {'ok': False, 'message': 'Bridge niedostępny lub nieprawidłowy token.'}
