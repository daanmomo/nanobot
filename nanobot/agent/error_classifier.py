"""API error classification for smart recovery.

Inspired by Hermes Agent's error_classifier.py.
Provides structured error taxonomy and recovery recommendations.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from loguru import logger


# ── Error taxonomy ──────────────────────────────────────────────────────

class FailoverReason(enum.Enum):
    """Why an API call failed — determines recovery strategy."""

    auth = "auth"                          # 401/403 — rotate credential
    auth_permanent = "auth_permanent"      # Auth failed after rotation — abort
    billing = "billing"                    # 402 or credit exhaustion — rotate/fallback
    rate_limit = "rate_limit"              # 429 — backoff then rotate
    overloaded = "overloaded"              # 503/529 — provider overloaded
    server_error = "server_error"          # 500/502 — retry
    timeout = "timeout"                    # Connection/read timeout — retry
    context_overflow = "context_overflow"  # Context too large — compress
    payload_too_large = "payload_too_large"  # 413 — compress
    model_not_found = "model_not_found"    # 404 — fallback model
    format_error = "format_error"          # 400 bad request — abort
    thinking_signature = "thinking_signature"  # Anthropic thinking block
    unknown = "unknown"                    # Unclassifiable — retry with backoff


# ── Classification result ───────────────────────────────────────────────

@dataclass
class ClassifiedError:
    """Structured classification with recovery hints."""

    reason: FailoverReason
    status_code: Optional[int] = None
    message: str = ""

    # Recovery action hints
    retryable: bool = True
    should_compress: bool = False
    should_rotate_credential: bool = False
    should_fallback: bool = False

    # Suggested retry delay (seconds)
    retry_delay: float = 1.0


# ── Pattern lists ───────────────────────────────────────────────────────

_BILLING_PATTERNS = [
    "insufficient credits", "insufficient_quota", "credit balance",
    "credits have been exhausted", "top up your credits",
    "payment required", "billing hard limit",
    "exceeded your current quota", "account is deactivated",
]

_RATE_LIMIT_PATTERNS = [
    "rate limit", "rate_limit", "too many requests", "throttled",
    "requests per minute", "tokens per minute", "try again in",
    "please retry after", "resource_exhausted",
]

_USAGE_LIMIT_PATTERNS = [
    "usage limit", "quota", "limit exceeded", "key limit exceeded",
]

_USAGE_LIMIT_TRANSIENT_SIGNALS = [
    "try again", "retry", "resets at", "reset in", "wait",
]

_CONTEXT_OVERFLOW_PATTERNS = [
    "context length", "context size", "maximum context",
    "token limit", "too many tokens", "reduce the length",
    "exceeds the limit", "context window", "prompt is too long",
    "max_tokens", "maximum number of tokens",
    "exceeds the max_model_len", "input is too long",
    "context length exceeded", "超过最大长度", "上下文长度",
]

_MODEL_NOT_FOUND_PATTERNS = [
    "is not a valid model", "invalid model", "model not found",
    "model_not_found", "does not exist", "no such model",
    "unknown model", "unsupported model",
]

_AUTH_PATTERNS = [
    "invalid api key", "invalid_api_key", "authentication",
    "unauthorized", "forbidden", "invalid token",
    "token expired", "access denied",
]

_TRANSPORT_ERROR_TYPES = frozenset({
    "ReadTimeout", "ConnectTimeout", "PoolTimeout",
    "ConnectError", "RemoteProtocolError",
    "ConnectionError", "ConnectionResetError",
    "APIConnectionError", "APITimeoutError",
})

_SERVER_DISCONNECT_PATTERNS = [
    "server disconnected", "peer closed connection",
    "connection reset by peer", "connection was closed",
    "unexpected eof", "incomplete chunked read",
]


# ── Classification pipeline ─────────────────────────────────────────────

def classify_api_error(
    error: Exception,
    *,
    approx_tokens: int = 0,
    context_length: int = 200000,
    num_messages: int = 0,
) -> ClassifiedError:
    """Classify an API error into a structured recovery recommendation.

    Priority-ordered pipeline:
      1. HTTP status code + message refinement
      2. Message pattern matching
      3. Transport error heuristics
      4. Server disconnect + large session → context overflow
      5. Fallback: unknown
    """
    status_code = _extract_status_code(error)
    error_type = type(error).__name__
    error_msg = _build_error_message(error).lower()

    def _result(reason: FailoverReason, **overrides) -> ClassifiedError:
        defaults = {
            "reason": reason,
            "status_code": status_code,
            "message": str(error)[:500],
        }
        defaults.update(overrides)
        return ClassifiedError(**defaults)

    # ── 1. Anthropic thinking signature (400 + "signature" + "thinking") ──
    if (status_code == 400 and "signature" in error_msg and "thinking" in error_msg):
        return _result(FailoverReason.thinking_signature, retryable=True)

    # ── 2. HTTP status code classification ──
    if status_code is not None:
        classified = _classify_by_status(status_code, error_msg, approx_tokens, context_length, num_messages, _result)
        if classified:
            return classified

    # ── 3. Message pattern matching ──
    classified = _classify_by_message(error_msg, approx_tokens, context_length, _result)
    if classified:
        return classified

    # ── 4. Server disconnect + large session → context overflow ──
    is_disconnect = any(p in error_msg for p in _SERVER_DISCONNECT_PATTERNS)
    if is_disconnect and not status_code:
        is_large = approx_tokens > context_length * 0.6 or num_messages > 200
        if is_large:
            return _result(FailoverReason.context_overflow, retryable=True, should_compress=True)
        return _result(FailoverReason.timeout, retryable=True, retry_delay=2.0)

    # ── 5. Transport / timeout ──
    if error_type in _TRANSPORT_ERROR_TYPES or isinstance(error, (TimeoutError, ConnectionError, OSError)):
        return _result(FailoverReason.timeout, retryable=True, retry_delay=2.0)

    # ── 6. Unknown ──
    return _result(FailoverReason.unknown, retryable=True, retry_delay=3.0)


def _classify_by_status(
    status_code: int, error_msg: str,
    approx_tokens: int, context_length: int, num_messages: int,
    result_fn,
) -> Optional[ClassifiedError]:
    """Classify based on HTTP status code."""

    if status_code == 401:
        return result_fn(FailoverReason.auth, retryable=False, should_rotate_credential=True, should_fallback=True)

    if status_code == 403:
        if "key limit exceeded" in error_msg or "spending limit" in error_msg:
            return result_fn(FailoverReason.billing, retryable=False, should_rotate_credential=True, should_fallback=True)
        return result_fn(FailoverReason.auth, retryable=False, should_fallback=True)

    if status_code == 402:
        # Disambiguate: billing exhaustion vs transient usage limit
        has_usage = any(p in error_msg for p in _USAGE_LIMIT_PATTERNS)
        has_transient = any(p in error_msg for p in _USAGE_LIMIT_TRANSIENT_SIGNALS)
        if has_usage and has_transient:
            return result_fn(FailoverReason.rate_limit, retryable=True, retry_delay=30.0, should_rotate_credential=True)
        return result_fn(FailoverReason.billing, retryable=False, should_rotate_credential=True, should_fallback=True)

    if status_code == 404:
        return result_fn(FailoverReason.model_not_found, retryable=False, should_fallback=True)

    if status_code == 413:
        return result_fn(FailoverReason.payload_too_large, retryable=True, should_compress=True)

    if status_code == 429:
        return result_fn(FailoverReason.rate_limit, retryable=True, retry_delay=10.0, should_rotate_credential=True)

    if status_code == 400:
        # Context overflow from 400
        if any(p in error_msg for p in _CONTEXT_OVERFLOW_PATTERNS):
            return result_fn(FailoverReason.context_overflow, retryable=True, should_compress=True)
        if any(p in error_msg for p in _MODEL_NOT_FOUND_PATTERNS):
            return result_fn(FailoverReason.model_not_found, retryable=False, should_fallback=True)
        if any(p in error_msg for p in _RATE_LIMIT_PATTERNS):
            return result_fn(FailoverReason.rate_limit, retryable=True, retry_delay=10.0)
        # Generic 400 + large session → probable context overflow
        is_large = approx_tokens > context_length * 0.4 or num_messages > 80
        if is_large:
            return result_fn(FailoverReason.context_overflow, retryable=True, should_compress=True)
        return result_fn(FailoverReason.format_error, retryable=False, should_fallback=True)

    if status_code in (500, 502):
        return result_fn(FailoverReason.server_error, retryable=True, retry_delay=3.0)

    if status_code in (503, 529):
        return result_fn(FailoverReason.overloaded, retryable=True, retry_delay=5.0)

    if 400 <= status_code < 500:
        return result_fn(FailoverReason.format_error, retryable=False, should_fallback=True)

    if 500 <= status_code < 600:
        return result_fn(FailoverReason.server_error, retryable=True, retry_delay=3.0)

    return None


def _classify_by_message(
    error_msg: str, approx_tokens: int, context_length: int, result_fn,
) -> Optional[ClassifiedError]:
    """Classify based on error message patterns."""

    # Billing
    if any(p in error_msg for p in _BILLING_PATTERNS):
        return result_fn(FailoverReason.billing, retryable=False, should_rotate_credential=True, should_fallback=True)

    # Rate limit
    if any(p in error_msg for p in _RATE_LIMIT_PATTERNS):
        return result_fn(FailoverReason.rate_limit, retryable=True, retry_delay=10.0, should_rotate_credential=True)

    # Context overflow
    if any(p in error_msg for p in _CONTEXT_OVERFLOW_PATTERNS):
        return result_fn(FailoverReason.context_overflow, retryable=True, should_compress=True)

    # Auth
    if any(p in error_msg for p in _AUTH_PATTERNS):
        return result_fn(FailoverReason.auth, retryable=False, should_rotate_credential=True, should_fallback=True)

    # Model not found
    if any(p in error_msg for p in _MODEL_NOT_FOUND_PATTERNS):
        return result_fn(FailoverReason.model_not_found, retryable=False, should_fallback=True)

    # Usage limit disambiguation
    has_usage = any(p in error_msg for p in _USAGE_LIMIT_PATTERNS)
    if has_usage:
        has_transient = any(p in error_msg for p in _USAGE_LIMIT_TRANSIENT_SIGNALS)
        if has_transient:
            return result_fn(FailoverReason.rate_limit, retryable=True, retry_delay=30.0)
        return result_fn(FailoverReason.billing, retryable=False, should_fallback=True)

    return None


# ── Helpers ─────────────────────────────────────────────────────────────

def _extract_status_code(error: Exception) -> Optional[int]:
    """Walk error chain to find HTTP status code."""
    current = error
    for _ in range(5):
        code = getattr(current, "status_code", None)
        if isinstance(code, int):
            return code
        code = getattr(current, "status", None)
        if isinstance(code, int) and 100 <= code < 600:
            return code
        cause = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
        if cause is None or cause is current:
            break
        current = cause
    return None


def _build_error_message(error: Exception) -> str:
    """Build comprehensive error message for pattern matching."""
    parts = [str(error)]
    # Extract body message if available
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        err_obj = body.get("error", {})
        if isinstance(err_obj, dict):
            msg = err_obj.get("message", "")
            if msg:
                parts.append(msg)
            # OpenRouter metadata.raw
            metadata = err_obj.get("metadata", {})
            if isinstance(metadata, dict):
                raw = metadata.get("raw", "")
                if raw:
                    parts.append(raw)
    return " ".join(parts)


def _extract_message(error: Exception) -> str:
    """Extract the most informative error message."""
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        err_obj = body.get("error", {})
        if isinstance(err_obj, dict):
            msg = err_obj.get("message", "")
            if msg:
                return str(msg)[:500]
    return str(error)[:500]
