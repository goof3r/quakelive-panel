#!/usr/bin/env bash
# ============================================================
#  install_bridge.sh — instaluje ZMQ Bridge jako usługę systemd
#  Uruchom na SERWERZE QL jako zwykły użytkownik (nie root)
# ============================================================
set -euo pipefail

BRIDGE_DIR="$(cd "$(dirname "$0")" && pwd)"
BRIDGE_PY="$BRIDGE_DIR/bridge.py"
BRIDGE_USER="$(whoami)"
SERVICE_NAME="qlpanel-bridge"
UNIT="/etc/systemd/system/${SERVICE_NAME}.service"

echo "[*] Quake Live ZMQ Bridge — instalator"
echo "[*] Katalog: $BRIDGE_DIR"
echo "[*] Użytkownik: $BRIDGE_USER"

# Zależności Python
echo "[*] Instaluję pyzmq..."
sudo -H env PIP_BREAK_SYSTEM_PACKAGES=1 python3 -m pip install -r "$BRIDGE_DIR/requirements.txt"
echo "[OK] Zależności zainstalowane."

# Konfiguracja bridge'a (generuje bridge_config.json przy pierwszym uruchomieniu)
if [ ! -f "$BRIDGE_DIR/bridge_config.json" ]; then
    echo "[*] Tworzę domyślny bridge_config.json (ZMIEŃ go przed uruchomieniem!)..."
    python3 "$BRIDGE_PY" &
    PID=$!
    sleep 1
    kill $PID 2>/dev/null || true
fi

# systemd unit
echo "[*] Tworzę usługę systemd: $UNIT"
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=Quake Live Panel ZMQ Bridge
After=network.target

[Service]
Type=simple
User=${BRIDGE_USER}
WorkingDirectory=${BRIDGE_DIR}
ExecStart=/usr/bin/python3 ${BRIDGE_PY}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable  "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo ""
echo "[OK] Bridge zainstalowany i uruchomiony jako: $SERVICE_NAME"
echo ""
echo "Polecenia:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "WAŻNE: Edytuj bridge_config.json i ustaw:"
echo "  - bearer_token (ten sam co BRIDGE_TOKEN w config.php panelu)"
echo "  - dane serwerów QL (host, porty, hasła rcon/stats)"
echo "  - sudo systemctl restart $SERVICE_NAME   po edycji"
