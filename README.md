# Hermes Kiro Auth (`hermes-kiro-auth`)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Hermes Agent](https://img.shields.io/badge/Hermes-Plugin-blue.svg)](https://hermesagent.com)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-green.svg)](https://kiro.dev)

> Native Hermes Agent plugin to seamlessly authenticate and query **Claude 3.7 Sonnet**, **Claude Opus 4.6**, **Claude 5**, and other frontier models using your **AWS Kiro (Amazon Q Developer / CodeWhisperer)** subscription.

---

## ✨ Features

- 🚀 **Zero-Config Self-Healing Gateway**: Automatically starts and stops the local gateway daemon on port `8997` with Hermes. No extra terminal tabs or background scripts required.
- 🔑 **Automatic Token & Profile Discovery**: Automatically finds and extracts your AWS SSO / Kiro credentials and CodeWhisperer profile ARN from your local `kiro-cli` SQLite database across macOS, Linux, and Windows.
- ⚡ **Ultra-Fast Token Streaming**: Unbuffered Server-Sent Events (SSE) streaming with sub-100ms first-token latency.
- 🛠️ **Hermes Model Selector Integration**: Integrates directly into the Hermes UI dropdown model picker as a first-class model provider.
- 🧠 **Extended Thinking & Reasoning**: Full support for reasoning effort controls (`Low`, `Med`, `High`, `Max`) inside Hermes.

---

## 🤖 Supported Models

| Model Name in Hermes | Family / Backend | Description |
|---|---|---|
| `auto-kiro` / `auto` | Auto-Routing | Dynamic model routing optimized by Kiro |
| `claude-sonnet-4.6` | Anthropic Claude | Claude 3.5 / 4.6 Sonnet (Thinking & Code) |
| `claude-sonnet-4.5` | Anthropic Claude | General coding & software development |
| `claude-sonnet-5` | Anthropic Claude | Next-generation Sonnet |
| `claude-opus-4.6` | Anthropic Claude | Deep reasoning, complex problem solving |
| `claude-opus-4.5` | Anthropic Claude | Complex planning & architecture |
| `claude-opus-5` | Anthropic Claude | Next-generation Opus |
| `claude-haiku-4.5` | Anthropic Claude | Fast, low-latency utility & simple tasks |
| `gpt-5.6-sol` | OpenAI GPT Foundation | Frontier reasoning & code synthesis |
| `gpt-5.6-terra` | OpenAI GPT Foundation | Terra variation |
| `gpt-5.6-luna` | OpenAI GPT Foundation | Luna variation |
| `minimax-m2.5` | MiniMax | Workflow planning & structured output |
| `minimax-m2.1` | MiniMax | MiniMax M2.1 general coding |
| `qwen3-coder-next` | Alibaba Qwen | Specialized coding & repository tasks |

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

---

## 🔍 Architecture Overview

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

---

## 🛠️ Troubleshooting

### 1. `kiro whoami` or missing session
Ensure you are logged into the Kiro CLI on your system:
```bash
kiro-cli auth login
# or
kiro login
```

### 2. Manual Verification
You can test the background gateway directly from your terminal:
```bash
curl http://127.0.0.1:8997/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock" \
  -d '{
    "model": "claude-sonnet-4.6",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
