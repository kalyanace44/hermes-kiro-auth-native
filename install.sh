#!/usr/bin/env bash
set -e

# ==============================================================================
# Hermes Kiro Auth Plugin Installer
# ==============================================================================

HERMES_DIR="$HOME/.hermes"
HERMES_PLUGINS_DIR="$HERMES_DIR/plugins"
HERMES_PROVIDERS_DIR="$HERMES_PLUGINS_DIR/model-providers"
CONFIG_FILE="$HERMES_DIR/config.yaml"

echo "📦 Installing Hermes Kiro Auth Plugin..."

# Create target directories
mkdir -p "$HERMES_PLUGINS_DIR/kiro"
mkdir -p "$HERMES_PROVIDERS_DIR/kiro"

# Copy plugin files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -rf "$SCRIPT_DIR/plugins/kiro/"* "$HERMES_PLUGINS_DIR/kiro/"
cp -rf "$SCRIPT_DIR/plugins/model-providers/kiro/"* "$HERMES_PROVIDERS_DIR/kiro/"

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

# Refresh running Hermes instances
PID=$(lsof -t -i:8999 2>/dev/null || true)
if [ -n "$PID" ]; then
    kill -9 "$PID" 2>/dev/null || true
fi

echo ""
echo "🎉 Installation complete!"
echo "👉 Reload Hermes (Cmd + R) to access AWS Kiro models in your model selector."
