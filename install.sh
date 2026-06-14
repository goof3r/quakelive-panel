#!/usr/bin/env bash
# ============================================================
#  Quake Live Server Panel — Instalator
#  Działa w obrębie bieżącego użytkownika.
#  sudo wymagane tylko do: apt install python3 (jeśli brak)
#
#  Użycie:
#    bash install.sh           — instalacja interaktywna
#    bash install.sh --service — instalacja + usługa systemd --user
#    bash install.sh --help
# ============================================================
set -euo pipefail

PANEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PANEL_DIR/venv"
SERVICE_NAME="qlpanel"
PORT="${PORT:-9999}"

c_ok="\033[1;32m"; c_warn="\033[1;33m"; c_err="\033[1;31m"
c_info="\033[1;36m"; c_acc="\033[1;33m"; c_end="\033[0m"
log()  { echo -e "${c_info}[*]${c_end} $*"; }
ok()   { echo -e "${c_ok}[OK]${c_end} $*"; }
warn() { echo -e "${c_warn}[!]${c_end} $*"; }
err()  { echo -e "${c_err}[X]${c_end} $*" >&2; }
die()  { err "$*"; exit 1; }

INSTALL_SERVICE=0
for arg in "$@"; do
  case "$arg" in
    --service) INSTALL_SERVICE=1 ;;
    --help|-h)
      echo "Użycie: bash install.sh [--service] [--help]"
      echo "  --service   Zainstaluj jako usługę systemd --user (autostart bez sudo)"
      exit 0 ;;
  esac
done

echo -e "\n${c_acc}  ╔══════════════════════════════════════════╗"
echo    "  ║   Quake Live Server Panel — Instalator  ║"
echo -e "  ╚══════════════════════════════════════════╝${c_end}\n"

log "Katalog panelu: $PANEL_DIR"

# ── 1. Sprawdź / zainstaluj Python 3.8+ ───────────────────────────────────────
log "Sprawdzam Python 3..."
if ! command -v python3 &>/dev/null; then
  warn "Python 3 nie znaleziony — instaluję przez apt..."
  sudo apt-get update -y && sudo apt-get install -y python3 python3-pip python3-venv
  ok "Python 3 zainstalowany."
else
  PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  ok "Python $PY_VER znaleziony."
  if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' 2>/dev/null; then
    :
  else
    die "Wymagany Python >= 3.8. Masz: $PY_VER. Zaktualizuj Python i spróbuj ponownie."
  fi
fi

# ── 2. Sprawdź python3-venv ────────────────────────────────────────────────────
log "Sprawdzam moduł venv..."
if ! python3 -m venv --help &>/dev/null; then
  warn "Brak modułu venv — instaluję python3-venv..."
  sudo apt-get install -y python3-venv || \
    pip3 install --user virtualenv || \
    die "Nie udało się zainstalować venv. Zainstaluj ręcznie: sudo apt install python3-venv"
fi

# ── 3. Utwórz virtual environment ─────────────────────────────────────────────
if [ -d "$VENV_DIR" ]; then
  log "Katalog venv/ już istnieje — aktualizuję..."
else
  log "Tworzę virtual environment w $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
fi
ok "Venv gotowy: $VENV_DIR"

# ── 4. Zainstaluj zależności Python ───────────────────────────────────────────
log "Instaluję zależności Python..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$PANEL_DIR/requirements.txt" --quiet
ok "Zależności zainstalowane: Flask, paramiko, bcrypt, requests"

# ── 5. Inicjuj bazę SQLite ────────────────────────────────────────────────────
log "Inicjuję bazę danych SQLite..."
cd "$PANEL_DIR"
"$VENV_DIR/bin/python" -c "
import sys
sys.path.insert(0, '.')
from database import init_db
init_db()
print('  panel.db gotowy.')
"
ok "Baza danych: $PANEL_DIR/panel.db"

# ── 6. Konfiguracja ───────────────────────────────────────────────────────────
if [ ! -f "$PANEL_DIR/config.py" ]; then
  log "Kopiuję config.example.py → config.py..."
  cp "$PANEL_DIR/config.example.py" "$PANEL_DIR/config.py"
  ok "config.py stworzony — edytuj go i uzupełnij dane SSH/bridge."
else
  log "config.py już istnieje — nie nadpisuję."
fi

# ── 7. Sprawdź klucz SSH ──────────────────────────────────────────────────────
SSH_KEY_DEFAULT="$HOME/.ssh/id_ed25519"
if [ ! -f "$SSH_KEY_DEFAULT" ]; then
  warn "Nie znaleziono klucza SSH: $SSH_KEY_DEFAULT"
  warn "Wygeneruj klucz SSH bez hasła:"
  warn "  ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N \"\""
  warn "  ssh-copy-id -i ~/.ssh/id_ed25519.pub USER@SERWER_QL"
fi

# ── 8. Opcjonalna usługa systemd --user ───────────────────────────────────────
if [ "$INSTALL_SERVICE" = "1" ]; then
  log "Instaluję usługę systemd --user (bez sudo)..."
  UNIT_DIR="$HOME/.config/systemd/user"
  mkdir -p "$UNIT_DIR"
  cat > "$UNIT_DIR/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Quake Live Server Panel
After=network.target

[Service]
Type=simple
WorkingDirectory=${PANEL_DIR}
ExecStart=${VENV_DIR}/bin/python ${PANEL_DIR}/panel.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable  "$SERVICE_NAME"
  systemctl --user restart "$SERVICE_NAME"
  ok "Usługa ${SERVICE_NAME} zainstalowana i uruchomiona (systemd --user)."
  echo ""
  echo -e "  ${c_info}Zarządzanie usługą:${c_end}"
  echo    "    systemctl --user status  $SERVICE_NAME"
  echo    "    systemctl --user restart $SERVICE_NAME"
  echo    "    journalctl --user -u $SERVICE_NAME -f"

  # Włącz lingering żeby usługa działała po reboocie (bez aktywnej sesji)
  echo ""
  if loginctl show-user "$(whoami)" 2>/dev/null | grep -q "Linger=yes"; then
    ok "Lingering już aktywny — panel uruchomi się automatycznie po reboocie."
  else
    log "Włączam lingering (panel działa po reboocie bez logowania)..."
    if sudo loginctl enable-linger "$(whoami)" 2>/dev/null; then
      ok "Lingering włączony — panel uruchomi się automatycznie po reboocie."
    else
      warn "Nie udało się włączyć lingering automatycznie."
      warn "Uruchom ręcznie (jednorazowo):"
      warn "  sudo loginctl enable-linger $(whoami)"
      warn "Bez tego usługa NIE uruchomi się po reboocie bez aktywnego logowania."
    fi
  fi
fi

# ── 9. Skrypt startowy (bez venv) ─────────────────────────────────────────────
START_SCRIPT="$PANEL_DIR/start.sh"
cat > "$START_SCRIPT" <<EOF
#!/usr/bin/env bash
# Szybki start panelu (bez instalacji)
cd "${PANEL_DIR}"
exec "${VENV_DIR}/bin/python" "${PANEL_DIR}/panel.py"
EOF
chmod +x "$START_SCRIPT"

# ── Podsumowanie ───────────────────────────────────────────────────────────────
echo ""
echo -e "${c_ok}╔══════════════════════════════════════════════════════╗${c_end}"
echo -e "${c_ok}║  Instalacja zakończona!                              ║${c_end}"
echo -e "${c_ok}╚══════════════════════════════════════════════════════╝${c_end}"
echo ""
echo -e "  ${c_acc}Następne kroki:${c_end}"
echo ""
echo    "  1. Uzupełnij konfigurację:"
echo -e "     ${c_info}nano ${PANEL_DIR}/config.py${c_end}"
echo    "     (SSH_HOST, SSH_USER, SSH_KEY, BRIDGE_TOKEN)"
echo ""
echo    "  2. Uruchom panel:"
echo -e "     ${c_info}./start.sh${c_end}                  # skrypt startowy"
echo -e "     ${c_info}${VENV_DIR}/bin/python panel.py${c_end}   # bezpośrednio"
echo ""
echo    "  3. Otwórz w przeglądarce:"
echo -e "     ${c_info}http://$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'SERVER_IP'):${PORT}${c_end}"
echo ""
echo    "  4. Pierwsze uruchomienie → kreator konfiguracji (krok 1/3)"
echo ""
if [ "$INSTALL_SERVICE" != "1" ]; then
  echo    "  Tip: Zainstaluj jako usługę (autostart po restarcie):"
  echo -e "     ${c_info}bash install.sh --service${c_end}"
  echo ""
fi
echo -e "  ${c_warn}WAŻNE: Usuń dostęp publiczny do portu ${PORT} jeśli panel"
echo -e "  zawiera wrażliwe dane (hasła rcon/stats). Użyj SSH tunnel"
echo -e "  lub ogranicz firewallem do swoich IP.${c_end}"
echo ""

# ── Wdrożenie bridge na serwerze QL ───────────────────────────────────────────
if [ -f "$PANEL_DIR/bridge/bridge.py" ]; then
  echo -e "  ${c_info}ZMQ Bridge (deploy na serwerze QL):${c_end}"
  echo    "  scp -r ${PANEL_DIR}/bridge/ USER@SERWER_QL:/home/USER/qlpanel-bridge/"
  echo    "  ssh USER@SERWER_QL 'bash /home/USER/qlpanel-bridge/install_bridge.sh'"
  echo ""
fi
