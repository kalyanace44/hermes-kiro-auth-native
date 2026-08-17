# Hermes Kiro Auth (`hermes-kiro-auth-native`)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Hermes Agent](https://img.shields.io/badge/Hermes-Plugin-blue.svg)](https://hermesagent.com)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-green.svg)](https://kiro.dev)

> Native Hermes Agent plugin to seamlessly authenticate and query **Claude 3.7 Sonnet**, **Claude Opus 4.6**, and other frontier models using your **AWS Kiro (Amazon Q Developer / CodeWhisperer)** subscription.

---

## ✨ Features

- 🚀 **Zero-Config Self-Healing Gateway**: Automatically starts and stops the local gateway daemon on port `8997` with Hermes. No extra terminal tabs or background scripts required.
- 🔑 **Automatic Token & Profile Discovery**: Automatically finds and extracts your AWS SSO / Kiro credentials and CodeWhisperer profile ARN from your local `kiro-cli` SQLite database.
- ⚡ **Ultra-Fast Token Streaming**: Unbuffered Server-Sent Events (SSE) streaming with sub-100ms first-token latency.
- 🛠️ **Hermes Model Selector Integration**: Integrates directly into the Hermes UI dropdown model picker as a first-class model provider.
- 🧠 **Extended Thinking & Reasoning**: Full support for reasoning effort controls (`Low`, `Med`, `High`, `Max`) inside Hermes.

---

## 🤖 Supported Models

| Model Name in Hermes | Backend Architecture | Description |
|---|---|---|
| `claude-sonnet-4.6` | Anthropic Claude 3.5 / 4.6 Sonnet | High intelligence, balanced speed & reasoning |
| `claude-sonnet-4.5` | Anthropic Claude 3.5 Sonnet | General coding & software development |
| `claude-opus-4.6` | Anthropic Claude 3 / 4.6 Opus | Deep reasoning, high-complexity tasks |
| `claude-opus-4.5` | Anthropic Claude 3 Opus | Complex planning & architecture |
| `claude-haiku-4.5` | Anthropic Claude 3.5 Haiku | Fast, low-latency utility & simple tasks |
| `gpt-5.6-sol` | OpenAI GPT-5 Foundation | Frontier reasoning & code synthesis |
| `minimax-m2.5` | MiniMax M2.5 | Workflow planning & structured output |
| `qwen3-coder-next` | Qwen3 Coder Next | Specialized coding & repository tasks |

---

## 📦 Quick Installation

### Option 1: One-Line Installer (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/kalyanace44/hermes-kiro-auth-native/main/install.sh | bash
```

### Option 2: Clone and Install

```bash
git clone https://github.com/kalyanace44/hermes-kiro-auth-native.git
cd hermes-kiro-auth-native
chmod +x install.sh && ./install.sh
```

### Option 2: Manual Installation

1. Copy the plugin files to your `~/.hermes/plugins/` folder:
```bash
mkdir -p ~/.hermes/plugins/kiro
mkdir -p ~/.hermes/plugins/model-providers/kiro

cp -r plugins/kiro/* ~/.hermes/plugins/kiro/
cp -r plugins/model-providers/kiro/* ~/.hermes/plugins/model-providers/kiro/
```

2. Add the `kiro` provider to `~/.hermes/config.yaml`:
```yaml
providers:
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
```

3. Restart Hermes or press **`Cmd + R`** to refresh your models!

---

## 🔍 How It Works

```
┌─────────────────┐       OpenAI SSE Stream        ┌────────────────────────┐
│  Hermes Agent   │  ────────────────────────────> │  Hermes Kiro Plugin    │
│  (Desktop / CLI)│  <──────────────────────────── │  (Port 8997)           │
└─────────────────┘                                └───────────┬────────────┘
                                                               │
                                         Reads AWS SSO / OIDC  │
                                         Token from SQLite DB  ▼
                                                   ┌────────────────────────┐
                                                   │  AWS Kiro Service      │
                                                   │  (Amazon Q Developer)  │
                                                   └────────────────────────┘
```

1. When Hermes starts, the plugin auto-discovers your active Kiro credentials from `~/Library/Application Support/kiro-cli/data.sqlite3`.
2. It launches a background lightweight gateway bridge on `127.0.0.1:8997`.
3. When you send messages or invoke agent tools, requests are mapped directly to the AWS CodeWhisperer/Kiro streaming endpoint using your active profile ARN.

---

## 🛠️ Prerequisites

- [Kiro IDE](https://kiro.dev) or `kiro-cli` installed and authenticated on your machine (`kiro whoami` succeeds).
- [Hermes Agent](https://hermesagent.com) v0.8+ installed.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
