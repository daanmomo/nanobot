# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

```bash
# Install (editable)
pip install -e .

# Install with optional features
pip install -e ".[dev]"               # dev tools (pytest, ruff)
pip install -e ".[finance]"           # stock/fund/forex tools (akshare, yfinance)
pip install -e ".[browser]"           # playwright automation
pip install -e ".[finance,browser]"   # multiple extras

# Run CLI
nanobot agent -m "message"     # single message
nanobot agent                  # interactive mode
nanobot gateway                # start gateway (channels + cron + heartbeat)
nanobot status                 # show config status

# Lint
ruff check nanobot/
ruff check --fix nanobot/

# Test
pytest                         # all tests
pytest tests/test_skills.py    # single file
pytest -k "test_name"          # by name pattern

# Count core lines (excludes channels/, cli/, providers/)
bash core_agent_lines.sh
```

## Architecture

```
nanobot/
├── agent/              # Core agent logic
│   ├── loop.py         # Main agent loop: message → LLM → tool execution → response
│   ├── context.py      # Builds system prompt from workspace files + memory + skills
│   ├── memory.py       # Persistent memory (workspace/memory/*.md)
│   ├── skills.py       # Skills loader (workspace/skills/ + nanobot/skills/)
│   ├── subagent.py     # Background task execution via spawn tool
│   └── tools/          # Tool implementations
│       ├── base.py     # Abstract Tool class with JSON Schema validation
│       ├── registry.py # ToolRegistry: register + execute tools
│       ├── filesystem.py, shell.py, web.py, spawn.py, cron.py, message.py
│       └── stock/, usstock/, fund/, forex/, news/, browser/  # optional tools
├── skills/             # Built-in skills (SKILL.md files)
├── channels/           # Chat integrations (telegram, discord, whatsapp, feishu, etc.)
├── bus/                # Message routing (InboundMessage → AgentLoop → OutboundMessage)
├── cron/               # Scheduled tasks
├── heartbeat/          # Periodic workspace/HEARTBEAT.md processing
├── providers/          # LLM provider abstraction
│   ├── registry.py     # ProviderSpec definitions (single source of truth)
│   └── litellm_provider.py  # LiteLLM wrapper
├── session/            # Conversation session persistence
├── config/             # Configuration schema + loader
└── cli/                # CLI commands (typer)
```

## Key Patterns

### Adding a New Tool

1. Create a class extending `Tool` in `nanobot/agent/tools/`:
```python
from nanobot.agent.tools.base import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "What this tool does"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"arg": {"type": "string", "description": "..."}},
            "required": ["arg"]
        }

    async def execute(self, **kwargs) -> str:
        return "result"
```

2. Register in `AgentLoop._register_default_tools()` (loop.py)

For optional tools (need extra dependencies), create a module with `{MODULE}_TOOLS` list and add to `_OPTIONAL_TOOL_MODULES` in loop.py.

### Adding a New LLM Provider

1. Add `ProviderSpec` to `PROVIDERS` tuple in `nanobot/providers/registry.py`
2. Add field to `ProvidersConfig` in `nanobot/config/schema.py`

The registry handles env vars, model prefixing, and status display automatically.

### Adding a New Channel

1. Create channel class extending `BaseChannel` in `nanobot/channels/`
2. Implement `start()`, `stop()`, message handling
3. Add config schema to `ChannelsConfig` in `config/schema.py`
4. Register in `ChannelManager.__init__()` (channels/manager.py)

### Creating a Skill

Skills are SKILL.md files in `nanobot/skills/{name}/` or `~/.nanobot/workspace/skills/{name}/`:

```markdown
---
name: my-skill
description: Brief description
metadata: '{"nanobot": {"requires": {"bins": ["git"]}, "always": false}}'
---

# My Skill

Instructions for the agent...
```

- `always: true` in metadata loads skill into every context
- `requires.bins` checks for required CLI tools
- Workspace skills override built-in skills of same name

## Configuration

Config file: `~/.nanobot/config.json`

Workspace: `~/.nanobot/workspace/` (customizable via config)

Key workspace files:
- `AGENTS.md` - Agent behavior instructions
- `SOUL.md` - Personality/identity
- `USER.md` - User preferences
- `HEARTBEAT.md` - Periodic tasks (checked every 30min)
- `memory/MEMORY.md` - Long-term memory
- `skills/` - Custom user skills

## Testing

```bash
pytest                                    # run all
pytest tests/test_skills.py -v            # verbose single file
pytest -k "browser"                       # tests matching pattern
pytest --asyncio-mode=auto                # default mode (in pyproject.toml)
```

Tests use `tmp_path` fixtures for temporary workspaces. Mock external dependencies.

## Code Style

- Python 3.11+
- Line length: 100 (ruff)
- Type hints throughout
- Async/await for I/O operations
- Loguru for logging (`from loguru import logger`)
