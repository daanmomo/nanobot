"""Doom Loop Detector — prevents agents from getting stuck in repetitive cycles.

Inspired by HuggingFace ml-intern's doom loop detection.
Monitors tool calls for repetitive patterns and injects corrective prompts.

Three detection dimensions:
1. Exact repeat: same tool + same args called N times
2. Result repeat: different args but identical results
3. Oscillation: alternating between two tools without progress
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ToolCallRecord:
    """A single tool call record for pattern detection."""
    tool_name: str
    args_hash: str
    result_hash: str
    iteration: int


# Response levels
LEVEL_OK = 0
LEVEL_WARN = 1       # Inject soft hint
LEVEL_ESCALATE = 2   # Inject strong redirect
LEVEL_BREAK = 3      # Force stop the loop


@dataclass
class DoomLoopDetector:
    """Detects and breaks repetitive agent loops.

    Args:
        warn_threshold: Number of exact repeats before warning (default 3).
        escalate_threshold: Number of exact repeats before escalation (default 5).
        break_threshold: Number of exact repeats before forced break (default 7).
        max_no_progress: Max total tool calls without new results (default 50).
        window_size: Number of recent calls to track (default 20).
    """

    warn_threshold: int = 3
    escalate_threshold: int = 5
    break_threshold: int = 7
    max_no_progress: int = 50
    window_size: int = 20

    # Internal state
    _history: deque = field(default_factory=lambda: deque(maxlen=20))
    _unique_results: set = field(default_factory=set)
    _total_calls: int = 0

    def __post_init__(self):
        self._history = deque(maxlen=self.window_size)
        self._unique_results = set()
        self._total_calls = 0

    def reset(self) -> None:
        """Reset detector state (call at start of new user turn)."""
        self._history.clear()
        self._unique_results.clear()
        self._total_calls = 0

    def record(
        self,
        tool_name: str,
        args: dict | str,
        result: str,
        iteration: int = 0,
    ) -> tuple[int, str | None]:
        """Record a tool call and check for doom loops.

        Args:
            tool_name: Name of the tool called.
            args: Tool arguments (dict or JSON string).
            result: Tool result string.
            iteration: Current loop iteration number.

        Returns:
            Tuple of (level, correction_message).
            level: LEVEL_OK/WARN/ESCALATE/BREAK
            correction_message: Message to inject, or None if OK.
        """
        # Hash args and result
        args_hash = self._hash(args)
        result_hash = self._hash(result)

        record = ToolCallRecord(
            tool_name=tool_name,
            args_hash=args_hash,
            result_hash=result_hash,
            iteration=iteration,
        )
        self._history.append(record)
        self._unique_results.add(result_hash)
        self._total_calls += 1

        # Check all patterns
        level, msg = self._check_exact_repeat(record)
        if level == LEVEL_OK:
            level, msg = self._check_result_repeat(record)
        if level == LEVEL_OK:
            level, msg = self._check_oscillation()
        if level == LEVEL_OK:
            level, msg = self._check_no_progress()

        if level > LEVEL_OK:
            logger.warning(
                f"[DoomLoop] Level {level} detected: {tool_name} "
                f"(total calls: {self._total_calls}, unique results: {len(self._unique_results)})"
            )

        return level, msg

    def _check_exact_repeat(self, current: ToolCallRecord) -> tuple[int, str | None]:
        """Check if the same tool+args is being called repeatedly."""
        consecutive = 0
        for record in reversed(list(self._history)):
            if record.tool_name == current.tool_name and record.args_hash == current.args_hash:
                consecutive += 1
            else:
                break

        if consecutive >= self.break_threshold:
            return LEVEL_BREAK, (
                f"🛑 [Loop Breaker] You have called `{current.tool_name}` with identical arguments "
                f"{consecutive} times in a row. STOP. Tell the user you are stuck and explain why."
            )
        elif consecutive >= self.escalate_threshold:
            return LEVEL_ESCALATE, (
                f"⚠️ [Loop Warning] You have called `{current.tool_name}` with the same arguments "
                f"{consecutive} times. This is not working. You MUST try a completely different approach:\n"
                f"1. Use a different tool entirely\n"
                f"2. Change your strategy\n"
                f"3. If truly stuck, tell the user what's blocking you"
            )
        elif consecutive >= self.warn_threshold:
            return LEVEL_WARN, (
                f"💡 [Hint] You've called `{current.tool_name}` {consecutive} times with similar arguments. "
                f"Consider trying a different approach or different parameters."
            )

        return LEVEL_OK, None

    def _check_result_repeat(self, current: ToolCallRecord) -> tuple[int, str | None]:
        """Check if different calls are producing the same result."""
        if len(self._history) < 5:
            return LEVEL_OK, None

        recent = list(self._history)[-5:]
        same_result_count = sum(
            1 for r in recent
            if r.result_hash == current.result_hash and r.tool_name == current.tool_name
        )

        if same_result_count >= 5:
            return LEVEL_ESCALATE, (
                f"⚠️ [Pattern Detected] Last 5 calls to `{current.tool_name}` all returned "
                f"the same result despite different arguments. The approach isn't working. "
                f"Try a fundamentally different method."
            )
        elif same_result_count >= 3:
            return LEVEL_WARN, (
                f"💡 [Hint] Multiple calls to `{current.tool_name}` are returning identical results. "
                f"You may need to change your approach entirely."
            )

        return LEVEL_OK, None

    def _check_oscillation(self) -> tuple[int, str | None]:
        """Check for A→B→A→B oscillation pattern."""
        if len(self._history) < 6:
            return LEVEL_OK, None

        recent = [r.tool_name for r in list(self._history)[-6:]]

        # Check for ABABAB pattern
        if len(set(recent)) == 2:
            a, b = list(set(recent))
            expected = [a, b] * 3 if recent[0] == a else [b, a] * 3
            if recent == expected or recent == list(reversed(expected)):
                return LEVEL_WARN, (
                    f"💡 [Oscillation Detected] You're alternating between `{a}` and `{b}` "
                    f"without making progress. Break the cycle — try a third approach or "
                    f"combine the information you already have."
                )

        return LEVEL_OK, None

    def _check_no_progress(self) -> tuple[int, str | None]:
        """Check if too many calls have been made without new results."""
        if self._total_calls >= self.max_no_progress:
            progress_ratio = len(self._unique_results) / self._total_calls
            if progress_ratio < 0.3:  # Less than 30% unique results
                return LEVEL_BREAK, (
                    f"🛑 [No Progress] {self._total_calls} tool calls made but only "
                    f"{len(self._unique_results)} unique results ({progress_ratio:.0%}). "
                    f"You are not making progress. Summarize what you've found and respond to the user."
                )

        return LEVEL_OK, None

    @staticmethod
    def _hash(data: Any) -> str:
        """Create a short hash of data for comparison."""
        if isinstance(data, dict):
            text = json.dumps(data, sort_keys=True, default=str)
        elif isinstance(data, str):
            text = data
        else:
            text = str(data)
        # Use first 16 chars of md5 — enough for dedup, not crypto
        return hashlib.md5(text.encode()).hexdigest()[:16]
