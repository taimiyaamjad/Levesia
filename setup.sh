#!/bin/bash
# =============================================================================
# Levesia VPS Setup — Ubuntu 22/24
# Run as root: sudo bash setup.sh
# =============================================================================
set -euo pipefail

LEVESIA_USER="levesia"
LEVESIA_HOME="/home/levesia"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "  Levesia VPS Installer — Ubuntu 22/24"
echo "============================================"

# 1. System packages
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    nodejs npm \
    golang \
    gcc g++ \
    default-jdk \
    ruby ruby-bundler \
    php-cli \
    zip unzip curl wget openssl \
    build-essential

# Rust
if ! command -v cargo &>/dev/null; then
    echo "[1/7] Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path
fi
echo "[1/7] Done."

# 2. Create system user
echo "[2/7] Creating user '$LEVESIA_USER'..."
id "$LEVESIA_USER" &>/dev/null || useradd -m -s /bin/bash "$LEVESIA_USER"
echo "Done."

# 3. Directories
echo "[3/7] Creating directory structure..."
for dir in workspace output logs skills prompts config backups; do
    mkdir -p "$LEVESIA_HOME/$dir"
done
chown -R "$LEVESIA_USER:$LEVESIA_USER" "$LEVESIA_HOME"
echo "Done."

# 4. Copy files
echo "[4/7] Copying bot files..."
cp -r "$SCRIPT_DIR/bot"     "$LEVESIA_HOME/"
cp -r "$SCRIPT_DIR/skills"  "$LEVESIA_HOME/"
cp -r "$SCRIPT_DIR/prompts" "$LEVESIA_HOME/"
cp -r "$SCRIPT_DIR/config"  "$LEVESIA_HOME/"
chown -R "$LEVESIA_USER:$LEVESIA_USER" "$LEVESIA_HOME"
chmod +x "$LEVESIA_HOME/skills/"*.sh 2>/dev/null || true
echo "Done."

# 5. Python venv
echo "[5/7] Setting up Python virtualenv..."
sudo -u "$LEVESIA_USER" python3 -m venv "$LEVESIA_HOME/venv"
sudo -u "$LEVESIA_USER" "$LEVESIA_HOME/venv/bin/pip" install -q --upgrade pip
sudo -u "$LEVESIA_USER" "$LEVESIA_HOME/venv/bin/pip" install -q \
    -r "$LEVESIA_HOME/bot/requirements.txt"
echo "Done."

# 6. systemd service
echo "[6/7] Installing systemd service..."
cat > /etc/systemd/system/levesia.service << EOF
[Unit]
Description=Levesia Discord Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$LEVESIA_USER
WorkingDirectory=$LEVESIA_HOME/bot
ExecStart=$LEVESIA_HOME/venv/bin/python bot.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable levesia
echo "Done."

# 7. Config check
echo "[7/7] Checking config..."
CONFIG_FILE="$LEVESIA_HOME/config/config.yaml"
if grep -q "<YOUR_DISCORD_BOT_TOKEN>" "$CONFIG_FILE"; then
    echo ""
    echo "  ⚠️  Edit config before starting:"
    echo "     nano $CONFIG_FILE"
    echo ""
    echo "  Required fields:"
    echo "    bot.token         → Discord bot token"
    echo "    bot.owner_id      → Your Discord user ID"
    echo "    groq.api_key      → Groq API key (free at console.groq.com)"
    echo ""
fi

echo ""
echo "============================================"
echo "  Installation Complete"
echo "============================================"
echo ""
echo "  1. Fill config:   nano $CONFIG_FILE"
echo "  2. Start:         systemctl start levesia"
echo "  3. Check logs:    journalctl -u levesia -f"
echo "  4. On Discord:    !help"
echo ""
