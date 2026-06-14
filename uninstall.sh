#!/usr/bin/env bash
# ============================================================
#  Quake Live Server Panel — Deinstalator
#
#  Użycie:
#    bash uninstall.sh          — interaktywny (pyta o każdy krok)
#    bash uninstall.sh --full   — usuwa wszystko bez pytania
#    bash uninstall.sh --help
# ============================================================
set -euo pipefail

PANEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="qlpanel"
UNIT_FILE="$HOME/.config/systemd/user/${SERVICE_NAME}.service"

c_ok="\033[1;32m"; c_warn="\033[1;33m"; c_err="\033[1;31m"
c_info="\033[1;36m"; c_acc="\033[1;33m"; c_end="\033[0m"
log()  { echo -e "${c_info}[*]${c_end} $*"; }
ok()   { echo -e "${c_ok}[OK]${c_end} $*"; }
warn() { echo -e "${c_warn}[!]${c_end} $*"; }
err()  { echo -e "${c_err}[X]${c_end} $*" >&2; }

FULL_MODE=0
for arg in "$@"; do
  case "$arg" in
    --full)   FULL_MODE=1 ;;
    --help|-h)
      echo "Użycie: bash uninstall.sh [--full] [--help]"
      echo "  --full   Usuwa wszystko bez pytania (venv, panel.db, config.py, usługa)"
      exit 0 ;;
  esac
done

ask() {
  # ask <pytanie> → 0=tak, 1=nie
  if [ "$FULL_MODE" = "1" ]; then return 0; fi
  local ans
  read -r -p "  $1 [T/n] " ans
  [[ "$ans" =~ ^[Nn]$ ]] && return 1 || return 0
}

echo -e "\n${c_acc}  ╔══════════════════════════════════════════╗"
echo    "  ║   Quake Live Server Panel — Odinstaluj  ║"
echo -e "  ╚══════════════════════════════════════════╝${c_end}\n"

if [ "$FULL_MODE" = "0" ]; then
  warn "Ten skrypt usunie dane panelu z: $PANEL_DIR"
  warn "Pliki źródłowe (panel.py, templates/, static/, bridge/) NIE zostaną usunięte"
  warn "chyba że wybierzesz opcję usunięcia całego katalogu na końcu."
  echo ""
fi

# ── 1. Zatrzymaj i wyłącz usługę systemd ─────────────────────────────────────
if systemctl --user list-unit-files "${SERVICE_NAME}.service" 2>/dev/null | grep -q "$SERVICE_NAME"; then
  log "Znaleziono usługę systemd: $SERVICE_NAME"
  if ask "Zatrzymać i wyłączyć usługę systemd --user '${SERVICE_NAME}'?"; then
    systemctl --user stop    "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
    ok "Usługa zatrzymana i wyłączona."
  fi
else
  log "Usługa systemd '${SERVICE_NAME}' nie jest zainstalowana — pomijam."
fi

# ── 2. Usuń plik unit ─────────────────────────────────────────────────────────
if [ -f "$UNIT_FILE" ]; then
  if ask "Usunąć plik usługi: $UNIT_FILE?"; then
    rm -f "$UNIT_FILE"
    systemctl --user daemon-reload 2>/dev/null || true
    ok "Plik unit usunięty."
  fi
fi

# ── 3. Usuń virtual environment ───────────────────────────────────────────────
if [ -d "$PANEL_DIR/venv" ]; then
  if ask "Usunąć katalog venv/ (~$(du -sh "$PANEL_DIR/venv" 2>/dev/null | cut -f1))?"; then
    rm -rf "$PANEL_DIR/venv"
    ok "venv/ usunięty."
  fi
fi

# ── 4. Usuń bazę danych ───────────────────────────────────────────────────────
if [ -f "$PANEL_DIR/panel.db" ]; then
  if ask "Usunąć bazę danych panel.db (użytkownicy, serwery, logi)?"; then
    rm -f "$PANEL_DIR/panel.db"
    ok "panel.db usunięty."
  fi
fi

# ── 5. Usuń plik konfiguracyjny ───────────────────────────────────────────────
if [ -f "$PANEL_DIR/config.py" ]; then
  if ask "Usunąć config.py (hasła, klucze, tokeny)?"; then
    rm -f "$PANEL_DIR/config.py"
    ok "config.py usunięty."
  fi
fi

# ── 6. Usuń skrypt startowy ───────────────────────────────────────────────────
if [ -f "$PANEL_DIR/start.sh" ]; then
  rm -f "$PANEL_DIR/start.sh"
  ok "start.sh usunięty."
fi

# ── 7. Wyczyść __pycache__ i *.pyc ───────────────────────────────────────────
log "Czyszczę pliki cache Python..."
find "$PANEL_DIR" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$PANEL_DIR" -name '*.pyc' -o -name '*.pyo' | xargs rm -f 2>/dev/null || true
ok "Cache Python wyczyszczony."

# ── 8. Opcjonalnie: wyłącz lingering ─────────────────────────────────────────
if loginctl show-user "$(whoami)" 2>/dev/null | grep -q "Linger=yes"; then
  if ask "Wyłączyć lingering dla użytkownika $(whoami)? (tylko jeśli nie używasz go do innych usług)"; then
    if sudo loginctl disable-linger "$(whoami)" 2>/dev/null; then
      ok "Lingering wyłączony."
    else
      warn "Nie udało się wyłączyć lingering — brak sudo. Uruchom ręcznie:"
      warn "  sudo loginctl disable-linger $(whoami)"
    fi
  fi
fi

# ── 9. Opcjonalnie: usuń cały katalog panelu ──────────────────────────────────
echo ""
if [ "$FULL_MODE" = "0" ]; then
  warn "Czy usunąć CAŁY katalog panelu?"
  warn "  $PANEL_DIR"
  warn "Spowoduje to usunięcie kodu źródłowego, szablonów, skryptów i bridge/."
  if ask "Usunąć cały katalog? (NIEODWRACALNE)"; then
    REMOVE_DIR=1
  else
    REMOVE_DIR=0
  fi
else
  REMOVE_DIR=1
fi

if [ "$REMOVE_DIR" = "1" ]; then
  # Kopiujemy ścieżkę bo za chwilę skrypt zostanie usunięty razem z katalogiem
  TARGET_DIR="$PANEL_DIR"
  echo -e "\n${c_err}Usuwam: $TARGET_DIR${c_end}"
  cd "$HOME"
  rm -rf "$TARGET_DIR"
  echo -e "${c_ok}[OK]${c_end} Katalog usunięty."
  echo -e "\n${c_ok}Odinstalowanie zakończone.${c_end}"
  exit 0
fi

# ── Podsumowanie ──────────────────────────────────────────────────────────────
echo ""
echo -e "${c_ok}╔══════════════════════════════════════════════════╗${c_end}"
echo -e "${c_ok}║  Odinstalowanie zakończone.                      ║${c_end}"
echo -e "${c_ok}╚══════════════════════════════════════════════════╝${c_end}"
echo ""
echo    "  Pliki źródłowe zachowane w: $PANEL_DIR"
echo    "  Aby ponownie zainstalować: bash install.sh"
echo    "  Aby usunąć katalog ręcznie: rm -rf $PANEL_DIR"
echo ""
