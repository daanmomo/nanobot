# nanobot

A lightweight personal AI assistant framework.

## Install

```bash
git clone https://github.com/HKUDS/nanobot.git
cd nanobot
pip install -e .
```

Install with optional features:

```bash
pip install -e ".[dev]"               # dev tools (pytest, ruff)
pip install -e ".[finance]"           # stock/fund/forex tools
pip install -e ".[browser]"           # playwright automation
pip install -e ".[finance,browser]"   # multiple extras
```

Or from PyPI:

```bash
pip install nanobot-ai
```

## Quick Start

**1. Initialize**

```bash
nanobot onboard
```

**2. Configure** (`~/.nanobot/config.json`)

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5"
    }
  }
}
```

**3. Chat**

```bash
nanobot agent -m "What is 2+2?"
nanobot agent                        # interactive mode
```

## Gateway (Channels + Cron)

Connect nanobot to chat platforms and run scheduled tasks:

```bash
nanobot gateway
```

Supported channels: Telegram, Discord, WhatsApp, Feishu, WeChat, WeCom, DingTalk, Slack, Email, QQ, Mochat.

Configure channels in `~/.nanobot/config.json` under `channels`. Each channel needs `enabled: true` plus platform-specific credentials.

## Local Models (vLLM)

```json
{
  "providers": {
    "vllm": {
      "apiKey": "dummy",
      "apiBase": "http://localhost:8000/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "meta-llama/Llama-3.1-8B-Instruct"
    }
  }
}
```

## Providers

| Provider | Get API Key |
|----------|-------------|
| `openrouter` | [openrouter.ai](https://openrouter.ai) |
| `anthropic` | [console.anthropic.com](https://console.anthropic.com) |
| `openai` | [platform.openai.com](https://platform.openai.com) |
| `deepseek` | [platform.deepseek.com](https://platform.deepseek.com) |
| `groq` | [console.groq.com](https://console.groq.com) |
| `gemini` | [aistudio.google.com](https://aistudio.google.com) |
| `minimax` | [platform.minimax.io](https://platform.minimax.io) |
| `dashscope` | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com) |
| `moonshot` | [platform.moonshot.cn](https://platform.moonshot.cn) |
| `zhipu` | [open.bigmodel.cn](https://open.bigmodel.cn) |
| `vllm` | Local (any OpenAI-compatible server) |

Adding a new provider takes 2 steps: add a `ProviderSpec` to `nanobot/providers/registry.py` and a field to `ProvidersConfig` in `nanobot/config/schema.py`.

## Architecture

```
nanobot/
├── agent/              # Core agent logic
│   ├── loop.py         # Agent loop: message -> LLM -> tool execution -> response
│   ├── context.py      # System prompt builder
│   ├── memory.py       # Persistent memory
│   ├── skills.py       # Skills loader
│   ├── subagent.py     # Background task execution
│   └── tools/          # Tool implementations
├── skills/             # Built-in skills (SKILL.md files)
├── channels/           # Chat integrations
├── bus/                # Message routing
├── cron/               # Scheduled tasks
├── heartbeat/          # Periodic tasks
├── providers/          # LLM provider abstraction
├── session/            # Conversation persistence
├── config/             # Configuration
└── cli/                # CLI commands
```

## Skills

Skills are markdown files (`SKILL.md`) that extend the agent's capabilities. Built-in skills live in `nanobot/skills/`, user skills in `~/.nanobot/workspace/skills/`.

Built-in skills include: browser automation, stock/fund/forex data, news, weather, GitHub, cron scheduling, tmux, research, and gstack integration (browse, QA, review, ship, retro).

## CLI Reference

| Command | Description |
|---------|-------------|
| `nanobot onboard` | Initialize config & workspace |
| `nanobot agent -m "..."` | Chat with the agent |
| `nanobot agent` | Interactive chat mode |
| `nanobot gateway` | Start gateway (channels + cron) |
| `nanobot status` | Show config status |
| `nanobot cron add` | Add scheduled task |
| `nanobot cron list` | List scheduled tasks |

## Docker

```bash
docker build -t nanobot .
docker run -v ~/.nanobot:/root/.nanobot -p 18790:18790 nanobot gateway
```

## Development

```bash
pip install -e ".[dev]"
ruff check nanobot/
pytest
```

## License

MIT
