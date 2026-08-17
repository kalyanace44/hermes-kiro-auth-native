#!/usr/bin/env bash
set -e

# ==============================================================================
# Hermes Kiro Auth Plugin Installer (Native)
# ==============================================================================

HERMES_DIR="$HOME/.hermes"
HERMES_PLUGINS_DIR="$HERMES_DIR/plugins"
HERMES_PROVIDERS_DIR="$HERMES_PLUGINS_DIR/model-providers"
CONFIG_FILE="$HERMES_DIR/config.yaml"

echo "📦 Installing Hermes Kiro Auth Plugin..."

# Check if we are running from web stream
if [ ! -d "plugins/kiro" ]; then
    echo "🌍 Running from web/remote stream. Downloading files from GitHub..."
    TEMP_DIR="/tmp/hermes-kiro-auth-temp"
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
    
    curl -fsSL https://github.com/kalyanace44/hermes-kiro-auth-native/archive/refs/heads/main.zip -o "$TEMP_DIR/repo.zip"
    unzip -q "$TEMP_DIR/repo.zip" -d "$TEMP_DIR"
    
    SRC_PATH="$TEMP_DIR/hermes-kiro-auth-native-main"
else
    SRC_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    TEMP_DIR=""
fi

# Create target directories
mkdir -p "$HERMES_PLUGINS_DIR/kiro"
mkdir -p "$HERMES_PROVIDERS_DIR/kiro"

# Copy plugin files
cp -rf "$SRC_PATH/plugins/kiro/"* "$HERMES_PLUGINS_DIR/kiro/"
cp -rf "$SRC_PATH/plugins/model-providers/kiro/"* "$HERMES_PROVIDERS_DIR/kiro/"

echo "⚙️ Configuring Hermes provider settings..."

# Append kiro provider to config.yaml if not present
if [ -f "$CONFIG_FILE" ]; then
    if ! grep -q "kiro:" "$CONFIG_FILE"; then
        cat << 'EOF' >> "$CONFIG_FILE"

  kiro:
    api_key: mock
    base_url: http://127.0.0.1:8997/v1
    default_model: claude-sonnet-4.6
    models:
      - claude-sonnet-4.6
      - claude-sonnet-4.5
      - claude-opus-4.6
      - claude-opus-4.5
      - claude-haiku-4.5
      - gpt-5.6-sol
      - minimax-m2.5
      - qwen3-coder-next
EOF
        echo "✅ Added Kiro provider to ~/.hermes/config.yaml"
    fi
fi

# Refresh running Kiro gateway instance
PID=$(lsof -t -i:8997 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "🔄 Restarting Kiro gateway daemon..."
    kill -9 "$PID" 2>/dev/null || true
fi

# Clean up temp files if created
if [ -n "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
fi

echo ""
echo "🎉 Installation complete!"
echo "👉 Reload Hermes (Cmd + R) to access AWS Kiro models in your model selector."
