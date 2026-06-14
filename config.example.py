# ============================================================
#  config.example.py — skopiuj jako config.py i uzupełnij
#  cp config.example.py config.py && nano config.py
# ============================================================

# --- SSH do serwera QL ---
SSH_HOST    = '1.2.3.4'          # IP / hostname serwera QL
SSH_PORT    = 22
SSH_USER    = 'qladmin'           # użytkownik SSH na serwerze QL
SSH_KEY     = '/home/user/.ssh/id_ed25519'  # klucz prywatny (bez hasła)
QLDS_DIR    = '/home/qladmin/qlds'          # katalog QLDS na serwerze QL
SSH_TIMEOUT = 10

# --- ZMQ Bridge (bridge.py na serwerze QL) ---
BRIDGE_URL   = 'http://127.0.0.1:8765'   # adres bridge'a (lub SSH tunnel)
BRIDGE_TOKEN = 'ZMIEN_TOKEN_BRIDGE'       # Bearer token z bridge_config.json
BRIDGE_TIMEOUT = 5

# --- Panel ---
SESSION_SECRET = 'ZMIEN_NA_LOSOWY_KLUCZ_MIN_64_ZNAKI_ABCDEF1234567890'
PANEL_TITLE    = 'QL Server Panel'
PORT           = 9999
HOST           = '0.0.0.0'       # nasłuchuj na wszystkich interfejsach
DEBUG          = False

# --- Bezpieczeństwo ---
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_TIME = 300          # sekundy blokady po błędnych próbach
