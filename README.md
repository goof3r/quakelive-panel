# Quake Live Server Panel

> [Polski](#polski) · [English](#english)

---

<a name="polski"></a>
# Polski

Panel administracyjny dla serwerów Quake Live — sterowanie przez SSH, podgląd statystyk ZMQ, panel admina.  
**Stack:** Python 3.8+, Flask, SQLite · ZMQ Bridge (Python, na serwerze QL)

---

## Wymagania

### Serwer panelu (osobna maszyna / VPS)
- Python 3.8+
- Klucz SSH bez hasła do serwera QL (`~/.ssh/id_ed25519`)
- Dostęp do portu bridge'a ZMQ (domyślnie 8765) — przez SSH tunnel lub bezpośrednio

> `install.sh` zainstaluje Python 3 przez `apt` jeśli go brakuje. Tylko ta komenda wymaga `sudo`.

### Serwer Quake Live
- Python 3.10+ (do bridge'a)
- `pip3 install pyzmq`
- minqlx z włączonymi ZMQ stats/rcon

---

## Instalacja

### 1. Pobierz repozytorium

```bash
git clone https://github.com/goof3r/quakelive-panel.git
cd quakelive-panel
```

### 2. Skonfiguruj panel

```bash
cp config.example.py config.py
nano config.py
```

| Zmienna | Opis |
|---|---|
| `SSH_HOST` | IP serwera Quake Live |
| `SSH_PORT` | Port SSH (domyślnie `22`) |
| `SSH_USER` | Użytkownik SSH (np. `qladmin`) |
| `SSH_KEY` | Ścieżka do klucza prywatnego (np. `~/.ssh/id_ed25519`) |
| `QLDS_DIR` | Katalog QLDS na serwerze QL (np. `/home/qladmin/qlds`) |
| `BRIDGE_URL` | Adres bridge'a (np. `http://127.0.0.1:8765`) |
| `BRIDGE_TOKEN` | Bearer token do bridge'a |
| `SESSION_SECRET` | Losowy klucz sesji — wygeneruj: `python3 -c "import secrets; print(secrets.token_hex(32))"` |

### 3. Uruchom instalator

```bash
bash install.sh
```

Instalator:
- sprawdza / instaluje Python 3.8+
- tworzy `venv/` z wszystkimi zależnościami (Flask, paramiko, bcrypt, requests)
- inicjuje bazę SQLite (`panel.db`)
- kopiuje `config.example.py → config.py` jeśli brak
- sprawdza klucz SSH

### 4. Uruchom panel

```bash
./start.sh
# lub:
./venv/bin/python panel.py
```

Panel dostępny na: **http://TWOJE_IP:9999**

---

## Autostart po reboocie

```bash
bash install.sh --service
```

Instaluje panel jako usługę `systemd --user` i próbuje automatycznie włączyć lingering (panel działa po reboocie bez aktywnej sesji SSH).

Jeśli automatyczny lingering nie zadziałał — uruchom raz ręcznie:
```bash
sudo loginctl enable-linger $(whoami)
```

```bash
# Zarządzanie usługą:
systemctl --user status  qlpanel
systemctl --user restart qlpanel
systemctl --user stop    qlpanel
journalctl --user -u qlpanel -f    # logi na żywo
```

---

## Instalacja ZMQ Bridge (na serwerze QL)

```bash
# Na maszynie z panelem — skopiuj bridge na serwer QL:
scp -r bridge/ qladmin@IP_SERWERA_QL:/home/qladmin/qlpanel-bridge/

# Na serwerze QL:
cd /home/qladmin/qlpanel-bridge
bash install_bridge.sh
```

`bridge_config.json` jest generowany automatycznie przy pierwszym uruchomieniu bridge'a.

### SSH Tunnel (jeśli bridge nie ma publicznego IP)

```bash
# Na maszynie z panelem — otwórz tunel:
ssh -N -L 8765:127.0.0.1:8765 qladmin@IP_SERWERA_QL -i ~/.ssh/id_ed25519
```

Ustaw w `config.py`: `BRIDGE_URL = 'http://127.0.0.1:8765'`

---

## Pierwsze uruchomienie — kreator konfiguracji

Jeśli `config.py` nie istnieje lub baza nie ma żadnych użytkowników, panel automatycznie przekierowuje do kreatora `/setup` (3 kroki):

1. **Konfiguracja SSH i bridge** — dane połączenia z serwerem QL
2. **Konto admina** — login i hasło pierwszego administratora
3. **Pierwszy serwer QL** — dodanie serwera do panelu

---

## Obsługa

### Dashboard
- Lista wszystkich serwerów z automatycznym odświeżaniem co 15 s
- Status serwera: online/offline, mapa, tryb gry, liczba graczy
- Szybkie akcje: **Start / Stop / Restart** (tylko admin)

### Szczegóły serwera (`/server/<id>`)
- Tabela graczy z pingiem i wynikiem
- Feed zdarzeń ZMQ (odświeżany co 5 s)
- Konsola rcon — wysyłanie komend bezpośrednio do serwera (tylko admin)

### Panel admina (`/admin/`)
- **Użytkownicy** — dodawanie, usuwanie, zmiana hasła, role (`admin` / `viewer`)
- **Serwery** — dodawanie, usuwanie, włączanie/wyłączanie serwerów w panelu
- **Logi akcji** — paginowana historia akcji z filtrowaniem po użytkowniku, akcji i serwerze

### Role użytkowników

| Rola | Dashboard | Szczegóły serwera | Sterowanie | Panel admina |
|---|---|---|---|---|
| `viewer` | ✓ | ✓ | ✗ | ✗ |
| `admin` | ✓ | ✓ | ✓ | ✓ |

---

## Odinstalowanie

```bash
bash uninstall.sh          # interaktywny — pyta o każdy krok
bash uninstall.sh --full   # usuwa wszystko bez pytania
```

| Element | Interaktywny | `--full` |
|---|---|---|
| Usługa systemd `qlpanel` | pyta | tak |
| Plik unit `~/.config/systemd/user/qlpanel.service` | pyta | tak |
| `venv/` (środowisko Python) | pyta | tak |
| `panel.db` (baza: użytkownicy, serwery, logi) | pyta | tak |
| `config.py` (hasła, tokeny, klucze) | pyta | tak |
| `start.sh`, `__pycache__`, `*.pyc` | tak | tak |
| Lingering systemd | pyta | pyta |
| Cały katalog panelu (kod źródłowy) | pyta | tak |

---

## Bezpieczeństwo

- `config.py` i `panel.db` są w `.gitignore` — **nie commituj ich nigdy**
- Klucz SSH: `chmod 600 ~/.ssh/id_ed25519`
- `BRIDGE_TOKEN` — silny losowy token: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- Port 9999: ogranicz firewallem do zaufanych IP lub używaj SSH tunelu
- Port bridge'a 8765: nie wystawiaj publicznie — dostęp tylko z IP panelu

---

## Struktura projektu

```
quakelive-panel/
├── panel.py               # entry point Flask
├── config.example.py      # szablon konfiguracji
├── config.py              # twój config (.gitignore)
├── database.py            # SQLite schema + helpers
├── auth.py                # bcrypt, sesje Flask, dekoratory
├── ssh_client.py          # Paramiko — sterowanie przez SSH
├── zmq_client.py          # HTTP client do bridge'a
├── requirements.txt       # Flask, paramiko, bcrypt, requests
├── install.sh             # instalator
├── uninstall.sh           # deinstalator
├── routes/
│   ├── main.py            # dashboard, login, setup wizard
│   ├── api.py             # AJAX endpoints (/api/*)
│   └── admin.py           # panel admina (/admin/*)
├── templates/             # Jinja2 — motyw Q3/QL
├── static/                # CSS, JS, SVG
└── bridge/                # deploy osobno na serwerze QL
    ├── bridge.py          # ZMQ → REST API
    ├── requirements.txt   # pyzmq
    └── install_bridge.sh
```

---
---

<a name="english"></a>
# English

Administrative panel for Quake Live servers — SSH control, ZMQ statistics, admin panel.  
**Stack:** Python 3.8+, Flask, SQLite · ZMQ Bridge (Python, runs on QL server)

---

## Requirements

### Panel server (separate machine / VPS)
- Python 3.8+
- Passwordless SSH key to the QL server (`~/.ssh/id_ed25519`)
- Access to ZMQ bridge port (default 8765) — via SSH tunnel or directly

> `install.sh` will install Python 3 via `apt` if missing. Only that step requires `sudo`.

### Quake Live server
- Python 3.10+ (for the bridge)
- `pip3 install pyzmq`
- minqlx with ZMQ stats/rcon enabled

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/goof3r/quakelive-panel.git
cd quakelive-panel
```

### 2. Configure the panel

```bash
cp config.example.py config.py
nano config.py
```

| Variable | Description |
|---|---|
| `SSH_HOST` | IP of the Quake Live server |
| `SSH_PORT` | SSH port (default `22`) |
| `SSH_USER` | SSH user (e.g. `qladmin`) |
| `SSH_KEY` | Path to private key (e.g. `~/.ssh/id_ed25519`) |
| `QLDS_DIR` | QLDS directory on QL server (e.g. `/home/qladmin/qlds`) |
| `BRIDGE_URL` | Bridge address (e.g. `http://127.0.0.1:8765`) |
| `BRIDGE_TOKEN` | Bearer token for the bridge |
| `SESSION_SECRET` | Random session key — generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |

### 3. Run the installer

```bash
bash install.sh
```

The installer:
- checks / installs Python 3.8+
- creates `venv/` with all dependencies (Flask, paramiko, bcrypt, requests)
- initializes the SQLite database (`panel.db`)
- copies `config.example.py → config.py` if missing
- checks the SSH key

### 4. Start the panel

```bash
./start.sh
# or:
./venv/bin/python panel.py
```

Panel available at: **http://YOUR_IP:9999**

---

## Autostart on reboot

```bash
bash install.sh --service
```

Installs the panel as a `systemd --user` service and automatically enables lingering (panel runs after reboot without an active SSH session).

If automatic lingering failed — run once manually:
```bash
sudo loginctl enable-linger $(whoami)
```

```bash
# Service management:
systemctl --user status  qlpanel
systemctl --user restart qlpanel
systemctl --user stop    qlpanel
journalctl --user -u qlpanel -f    # live logs
```

---

## ZMQ Bridge installation (on the QL server)

```bash
# From the panel machine — copy bridge to QL server:
scp -r bridge/ qladmin@QL_SERVER_IP:/home/qladmin/qlpanel-bridge/

# On the QL server:
cd /home/qladmin/qlpanel-bridge
bash install_bridge.sh
```

`bridge_config.json` is generated automatically on first bridge start.

### SSH Tunnel (if bridge has no public IP)

```bash
# On the panel machine — open tunnel:
ssh -N -L 8765:127.0.0.1:8765 qladmin@QL_SERVER_IP -i ~/.ssh/id_ed25519
```

Set in `config.py`: `BRIDGE_URL = 'http://127.0.0.1:8765'`

---

## First run — setup wizard

If `config.py` does not exist or the database has no users, the panel automatically redirects to the `/setup` wizard (3 steps):

1. **SSH & bridge configuration** — connection details for the QL server
2. **Admin account** — login and password for the first administrator
3. **First QL server** — add a server to the panel

---

## Usage

### Dashboard
- List of all servers with auto-refresh every 15 s
- Server status: online/offline, map, game type, player count
- Quick actions: **Start / Stop / Restart** (admin only)

### Server detail (`/server/<id>`)
- Player table with ping and score
- ZMQ event feed (refreshed every 5 s)
- Rcon console — send commands directly to the server (admin only)

### Admin panel (`/admin/`)
- **Users** — add, delete, change password, set roles (`admin` / `viewer`)
- **Servers** — add, delete, enable/disable servers in the panel
- **Action logs** — paginated history with filtering by user, action, and server

### User roles

| Role | Dashboard | Server detail | Control | Admin panel |
|---|---|---|---|---|
| `viewer` | ✓ | ✓ | ✗ | ✗ |
| `admin` | ✓ | ✓ | ✓ | ✓ |

---

## Uninstallation

```bash
bash uninstall.sh          # interactive — asks about each step
bash uninstall.sh --full   # removes everything without prompting
```

| Item | Interactive | `--full` |
|---|---|---|
| systemd service `qlpanel` | asks | yes |
| Unit file `~/.config/systemd/user/qlpanel.service` | asks | yes |
| `venv/` (Python environment) | asks | yes |
| `panel.db` (database: users, servers, logs) | asks | yes |
| `config.py` (passwords, tokens, keys) | asks | yes |
| `start.sh`, `__pycache__`, `*.pyc` | yes | yes |
| systemd lingering | asks | asks |
| Entire panel directory (source code) | asks | yes |

---

## Security

- `config.py` and `panel.db` are in `.gitignore` — **never commit them**
- SSH key permissions: `chmod 600 ~/.ssh/id_ed25519`
- `BRIDGE_TOKEN` — strong random token: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- Port 9999: restrict by firewall to trusted IPs or use SSH tunnel
- Bridge port 8765: do not expose publicly — allow only from panel IP

---

## Project structure

```
quakelive-panel/
├── panel.py               # Flask entry point
├── config.example.py      # config template
├── config.py              # your config (.gitignore)
├── database.py            # SQLite schema + helpers
├── auth.py                # bcrypt, Flask sessions, decorators
├── ssh_client.py          # Paramiko — SSH server control
├── zmq_client.py          # HTTP client to bridge
├── requirements.txt       # Flask, paramiko, bcrypt, requests
├── install.sh             # installer
├── uninstall.sh           # uninstaller
├── routes/
│   ├── main.py            # dashboard, login, setup wizard
│   ├── api.py             # AJAX endpoints (/api/*)
│   └── admin.py           # admin panel (/admin/*)
├── templates/             # Jinja2 — Q3/QL theme
├── static/                # CSS, JS, SVG
└── bridge/                # deploy separately on QL server
    ├── bridge.py          # ZMQ → REST API
    ├── requirements.txt   # pyzmq
    └── install_bridge.sh
```
