# Hermes Kiro Auth (`hermes-kiro-auth-native`)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Hermes Agent](https://img.shields.io/badge/Hermes-Plugin-blue.svg)](https://hermesagent.com)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-green.svg)](https://kiro.dev)

> Native Hermes Agent plugin to seamlessly authenticate and query **Claude 3.7 Sonnet**, **Claude Opus 4.8**, **Claude 5**, **GPT-5.6**, and other frontier models directly using your **AWS Kiro (Amazon Q Developer / CodeWhisperer)** subscription with an isolated, dedicated authentication store.

---

## ✨ Features

- 🔒 **Isolated Authentication Store**: Independent `~/.hermes/kiro-auth.sqlite3` and `~/.hermes/kiro-accounts.json` storage to prevent any session conflicts with Kiro IDE or local tools.
- 🚀 **Zero-Config Self-Healing Gateway**: Automatically manages the local gateway daemon on port `8997` with Hermes.
- 🔑 **Automatic Token & Profile Discovery**: Automatically finds and extracts your AWS SSO / Kiro credentials and CodeWhisperer profile ARN on first setup, with direct SSO device login available anytime.
- 🔄 **Dynamic Model Discovery**: Real-time querying of the full live model catalogue directly from the AWS Kiro service.
- ⚡ **Ultra-Fast Token Streaming**: Unbuffered Server-Sent Events (SSE) streaming with sub-100ms first-token latency.
- 🛠️ **Hermes Model Selector Integration**: Integrates directly into the Hermes UI dropdown model picker as a first-class model provider.
- 🧠 **Extended Thinking & Reasoning**: Full support for reasoning effort controls (`Low`, `Med`, `High`, `Max`) inside Hermes.

---

## 🤖 Supported Models (19 Models)

| Model Name in Hermes | Family / Backend | Description |
|---|---|---|
| `claude-sonnet-4.6` | Anthropic Claude | Claude 3.5 / 4.6 Sonnet (Thinking & High-speed Code) |
| `claude-sonnet-4.5` | Anthropic Claude | General coding & software development |
| `claude-sonnet-5` | Anthropic Claude | Next-generation Sonnet |
| `claude-sonnet-4` | Anthropic Claude | Claude Sonnet 4 base |
| `claude-3.7-sonnet` | Anthropic Claude | Claude 3.7 Sonnet with hybrid reasoning |
| `claude-opus-5` | Anthropic Claude | Next-generation Opus |
| `claude-opus-4.8` | Anthropic Claude | Opus 4.8 frontier reasoning |
| `claude-opus-4.7` | Anthropic Claude | Opus 4.7 deep architecture |
| `claude-opus-4.6` | Anthropic Claude | Deep reasoning, complex problem solving |
| `claude-opus-4.5` | Anthropic Claude | Complex planning & architecture |
| `claude-haiku-4.5` | Anthropic Claude | Fast, low-latency utility & simple tasks |
| `gpt-5.6-sol` | OpenAI GPT Foundation | Frontier reasoning & code synthesis |
| `gpt-5.6-terra` | OpenAI GPT Foundation | Terra variation |
| `gpt-5.6-luna` | OpenAI GPT Foundation | Luna variation |
| `minimax-m2.5` | MiniMax | Workflow planning & structured output |
| `minimax-m2.1` | MiniMax | MiniMax M2.1 general coding |
| `qwen3-coder-next` | Alibaba Qwen | Specialized coding & repository tasks |
| `auto-kiro` | Auto-Routing | Dynamic model routing optimized by Kiro |
| `auto` | Auto-Routing | General auto-routing |

---

## 💬 Slash Commands & CLI

Manage your AWS Kiro account directly inside Hermes chat or terminal:

| Slash Command | CLI Equivalent | Description |
|---|---|---|
| `/kiro` or `/kiro-accounts` | `hermes kiro accounts` | View configured accounts, regions, token lifetime, and gateway health |
| `/kiro-login [region] [url]` | `hermes kiro login` | Authenticate directly via AWS SSO device authorization in your browser |
| `/kiro-reload` | `hermes kiro reload` | Refresh token and restart the local gateway daemon |
| `/kiro-import` | `hermes kiro import` | Force re-import credentials from local Kiro CLI / IDE into isolated store |

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
                                          Reads AWS SSO / OIDC │ (Isolated Store:
                                          Token from SQLite DB │  ~/.hermes/kiro-auth.sqlite3)
                                                               ▼
                                                   ┌────────────────────────┐
                                                   │  AWS Kiro Service      │
                                                   │  (Amazon Q Developer)  │
                                                   └────────────────────────┘
```

---

## 🛠️ Verification & Testing

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
