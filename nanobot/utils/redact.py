"""Regex-based secret redaction for logs and tool output.

Ported from Hermes Agent (agent/redact.py) with adaptations for nanobot:
- Uses loguru instead of stdlib logging
- Simplified env toggle
- Same 30+ pattern coverage

Applies pattern matching to mask API keys, tokens, and credentials
before they reach log files, tool output, or message channels.

Short tokens (< 18 chars) are fully masked. Longer tokens preserve
the first 6 and last 4 characters for debuggability.
"""

from __future__ import annotations

import os
import re

from loguru import logger

# Snapshot at import time so runtime env mutations cannot disable redaction mid-session.
_REDACT_ENABLED = os.getenv("NANOBOT_REDACT_SECRETS", "").lower() not in ("0", "false", "no", "off")

# ── Known API key prefixes ──────────────────────────────────────────────
_PREFIX_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{10,}",           # OpenAI / OpenRouter / Anthropic (sk-ant-*)
    r"ghp_[A-Za-z0-9]{10,}",            # GitHub PAT (classic)
    r"github_pat_[A-Za-z0-9_]{10,}",    # GitHub PAT (fine-grained)
    r"gho_[A-Za-z0-9]{10,}",            # GitHub OAuth access token
    r"ghu_[A-Za-z0-9]{10,}",            # GitHub user-to-server token
    r"ghs_[A-Za-z0-9]{10,}",            # GitHub server-to-server token
    r"ghr_[A-Za-z0-9]{10,}",            # GitHub refresh token
    r"xox[baprs]-[A-Za-z0-9-]{10,}",    # Slack tokens
    r"AIza[A-Za-z0-9_-]{30,}",          # Google API keys
    r"pplx-[A-Za-z0-9]{10,}",           # Perplexity
    r"fal_[A-Za-z0-9_-]{10,}",          # Fal.ai
    r"fc-[A-Za-z0-9]{10,}",             # Firecrawl
    r"bb_live_[A-Za-z0-9_-]{10,}",      # BrowserBase
    r"gAAAA[A-Za-z0-9_=-]{20,}",        # Codex encrypted tokens
    r"AKIA[A-Z0-9]{16}",                # AWS Access Key ID
    r"sk_live_[A-Za-z0-9]{10,}",        # Stripe secret key (live)
    r"sk_test_[A-Za-z0-9]{10,}",        # Stripe secret key (test)
    r"rk_live_[A-Za-z0-9]{10,}",        # Stripe restricted key
    r"SG\.[A-Za-z0-9_-]{10,}",          # SendGrid API key
    r"hf_[A-Za-z0-9]{10,}",             # HuggingFace token
    r"r8_[A-Za-z0-9]{10,}",             # Replicate API token
    r"npm_[A-Za-z0-9]{10,}",            # npm access token
    r"pypi-[A-Za-z0-9_-]{10,}",         # PyPI API token
    r"dop_v1_[A-Za-z0-9]{10,}",         # DigitalOcean PAT
    r"doo_v1_[A-Za-z0-9]{10,}",         # DigitalOcean OAuth
    r"am_[A-Za-z0-9_-]{10,}",           # AgentMail API key
    r"sk_[A-Za-z0-9_]{10,}",            # ElevenLabs TTS key
    r"tvly-[A-Za-z0-9]{10,}",           # Tavily search API key
    r"exa_[A-Za-z0-9]{10,}",            # Exa search API key
    r"gsk_[A-Za-z0-9]{10,}",            # Groq Cloud API key
    r"syt_[A-Za-z0-9]{10,}",            # Matrix access token
    r"retaindb_[A-Za-z0-9]{10,}",       # RetainDB API key
    r"hsk-[A-Za-z0-9]{10,}",            # Hindsight API key
    r"mem0_[A-Za-z0-9]{10,}",           # Mem0 Platform API key
    r"brv_[A-Za-z0-9]{10,}",            # ByteRover API key
    # Feishu / Lark app secrets
    r"cli_[A-Za-z0-9]{10,}",            # Feishu app ID
    r"t-[A-Za-z0-9]{20,}",              # Feishu tenant access token
]

# ── ENV assignment patterns ─────────────────────────────────────────────
_SECRET_ENV_NAMES = r"(?:API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH)"
_ENV_ASSIGN_RE = re.compile(
    rf"([A-Z0-9_]{{0,50}}{_SECRET_ENV_NAMES}[A-Z0-9_]{{0,50}})\s*=\s*(['\"]?)(\S+)\2",
)

# ── JSON field patterns ─────────────────────────────────────────────────
_JSON_KEY_NAMES = (
    r"(?:api_?[Kk]ey|token|secret|password|access_token|refresh_token|"
    r"auth_token|bearer|secret_value|raw_secret|secret_input|key_material|app_secret)"
)
_JSON_FIELD_RE = re.compile(
    rf'("{_JSON_KEY_NAMES}")\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)

# ── Authorization headers ───────────────────────────────────────────────
_AUTH_HEADER_RE = re.compile(
    r"(Authorization:\s*Bearer\s+)(\S+)",
    re.IGNORECASE,
)

# ── Telegram bot tokens ─────────────────────────────────────────────────
_TELEGRAM_RE = re.compile(
    r"(bot)?(\d{8,}):([-A-Za-z0-9_]{30,})",
)

# ── Private key blocks ──────────────────────────────────────────────────
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN[A-Z ]*PRIVATE KEY-----[\s\S]*?-----END[A-Z ]*PRIVATE KEY-----"
)

# ── Database connection strings ─────────────────────────────────────────
_DB_CONNSTR_RE = re.compile(
    r"((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:]+:)([^@]+)(@)",
    re.IGNORECASE,
)

# ── JWT tokens ──────────────────────────────────────────────────────────
_JWT_RE = re.compile(
    r"eyJ[A-Za-z0-9_-]{10,}"
    r"(?:\.[A-Za-z0-9_=-]{4,}){0,2}"
)

# ── Discord mentions ────────────────────────────────────────────────────
_DISCORD_MENTION_RE = re.compile(r"<@!?(\d{17,20})>")

# ── Phone numbers (E.164) ──────────────────────────────────────────────
_SIGNAL_PHONE_RE = re.compile(r"(\+[1-9]\d{6,14})(?![A-Za-z0-9])")

# ── Chinese phone numbers ──────────────────────────────────────────────
_CN_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")

# ── Compile known prefix patterns ──────────────────────────────────────
_PREFIX_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(" + "|".join(_PREFIX_PATTERNS) + r")(?![A-Za-z0-9_-])"
)


def _mask_token(token: str) -> str:
    """Mask a token, preserving prefix for long tokens."""
    if len(token) < 18:
        return "***"
    return f"{token[:6]}...{token[-4:]}"


def redact(text: str | None) -> str:
    """Apply all redaction patterns to a block of text.

    Safe to call on any string — non-matching text passes through unchanged.
    Disabled when NANOBOT_REDACT_SECRETS=false.

    Args:
        text: Input text (may be None).

    Returns:
        Redacted text.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return text
    if not _REDACT_ENABLED:
        return text

    # Known prefixes (sk-, ghp_, etc.)
    text = _PREFIX_RE.sub(lambda m: _mask_token(m.group(1)), text)

    # ENV assignments: OPENAI_API_KEY=sk-abc...
    def _redact_env(m):
        name, quote, value = m.group(1), m.group(2), m.group(3)
        return f"{name}={quote}{_mask_token(value)}{quote}"
    text = _ENV_ASSIGN_RE.sub(_redact_env, text)

    # JSON fields: "apiKey": "value"
    def _redact_json(m):
        key, value = m.group(1), m.group(2)
        return f'{key}: "{_mask_token(value)}"'
    text = _JSON_FIELD_RE.sub(_redact_json, text)

    # Authorization headers
    text = _AUTH_HEADER_RE.sub(
        lambda m: m.group(1) + _mask_token(m.group(2)),
        text,
    )

    # Telegram bot tokens
    def _redact_telegram(m):
        prefix = m.group(1) or ""
        digits = m.group(2)
        return f"{prefix}{digits}:***"
    text = _TELEGRAM_RE.sub(_redact_telegram, text)

    # Private key blocks
    text = _PRIVATE_KEY_RE.sub("[REDACTED PRIVATE KEY]", text)

    # Database connection string passwords
    text = _DB_CONNSTR_RE.sub(lambda m: f"{m.group(1)}***{m.group(3)}", text)

    # JWT tokens
    text = _JWT_RE.sub(lambda m: _mask_token(m.group(0)), text)

    # Discord mentions
    text = _DISCORD_MENTION_RE.sub(
        lambda m: f"<@{'!' if '!' in m.group(0) else ''}***>", text
    )

    # E.164 phone numbers
    def _redact_phone(m):
        phone = m.group(1)
        if len(phone) <= 8:
            return phone[:2] + "****" + phone[-2:]
        return phone[:4] + "****" + phone[-4:]
    text = _SIGNAL_PHONE_RE.sub(_redact_phone, text)

    # Chinese phone numbers (13x-19x)
    text = _CN_PHONE_RE.sub(lambda m: m.group(1)[:3] + "****" + m.group(1)[-4:], text)

    return text


def redact_tool_output(tool_name: str, output: str | None) -> str:
    """Redact tool output, with extra caution for shell/exec tools.

    Args:
        tool_name: Name of the tool that produced the output.
        output: Raw tool output.

    Returns:
        Redacted output string.
    """
    if output is None:
        return ""
    return redact(output)
