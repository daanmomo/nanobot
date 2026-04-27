"""Context compressor for managing conversation length.

Inspired by Hermes Agent's ContextCompressor.
When token usage exceeds a threshold, compress middle messages into a summary.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English, ~2 for Chinese."""
    if not text:
        return 0
    # Count CJK characters
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    ascii_count = len(text) - cjk_count
    return (ascii_count // 4) + (cjk_count // 2)


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate total tokens in a message list."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    total += estimate_tokens(item.get("text", ""))
        # Tool calls
        tool_calls = msg.get("tool_calls", [])
        for tc in tool_calls:
            if isinstance(tc, dict):
                func = tc.get("function", {})
                total += estimate_tokens(func.get("name", ""))
                total += estimate_tokens(func.get("arguments", ""))
    return total


class ContextCompressor:
    """Manages conversation context length by compressing when needed.

    Strategy:
    1. Monitor token usage after each LLM call
    2. When usage exceeds threshold, compress middle messages
    3. Keep system prompt + first N messages + last N messages
    4. Replace middle with a summary

    Args:
        max_context_tokens: Maximum context window size.
        compress_threshold: Fraction of max_context at which to compress (0.0-1.0).
        keep_first: Number of messages to preserve at the start (after system).
        keep_last: Number of messages to preserve at the end.
    """

    def __init__(
        self,
        max_context_tokens: int = 200000,
        compress_threshold: float = 0.5,
        keep_first: int = 2,
        keep_last: int = 10,
    ):
        self.max_context_tokens = max_context_tokens
        self.compress_threshold = compress_threshold
        self.keep_first = keep_first
        self.keep_last = keep_last
        self.compression_count = 0
        self.last_token_estimate = 0

    def should_compress(self, messages: list[dict[str, Any]], usage: dict | None = None) -> bool:
        """Check if context needs compression.

        Args:
            messages: Current message list.
            usage: Optional usage dict from LLM response (prompt_tokens, etc.).

        Returns:
            True if compression is needed.
        """
        # Use actual token count from API if available
        if usage:
            prompt_tokens = usage.get("prompt_tokens", 0)
            if prompt_tokens > 0:
                self.last_token_estimate = prompt_tokens
                threshold = int(self.max_context_tokens * self.compress_threshold)
                if prompt_tokens > threshold:
                    logger.info(
                        f"[Compressor] Token usage {prompt_tokens:,} exceeds threshold "
                        f"{threshold:,} ({self.compress_threshold:.0%} of {self.max_context_tokens:,})"
                    )
                    return True
                return False

        # Fallback: estimate from message content
        estimated = estimate_messages_tokens(messages)
        self.last_token_estimate = estimated
        threshold = int(self.max_context_tokens * self.compress_threshold)
        if estimated > threshold:
            logger.info(
                f"[Compressor] Estimated tokens {estimated:,} exceeds threshold {threshold:,}"
            )
            return True
        return False

    def compress(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Compress messages by summarizing the middle portion.

        Preserves:
        - System message (index 0)
        - First N user/assistant exchanges
        - Last N messages (recent context)

        Replaces middle with a structured summary.

        Args:
            messages: Full message list.

        Returns:
            Compressed message list.
        """
        if len(messages) <= self.keep_first + self.keep_last + 2:
            logger.info("[Compressor] Too few messages to compress, skipping")
            return messages

        self.compression_count += 1

        # Split: system + first_kept + middle + last_kept
        system_msg = messages[0] if messages[0]["role"] == "system" else None
        start_idx = 1 if system_msg else 0

        first_end = start_idx + self.keep_first
        last_start = len(messages) - self.keep_last

        if first_end >= last_start:
            logger.info("[Compressor] Overlap between first/last, skipping")
            return messages

        first_msgs = messages[start_idx:first_end]
        middle_msgs = messages[first_end:last_start]
        last_msgs = messages[last_start:]

        # Build summary of middle messages
        summary = self._summarize_messages(middle_msgs)

        logger.info(
            f"[Compressor] Compressed {len(middle_msgs)} middle messages into summary "
            f"(compression #{self.compression_count})"
        )

        # Reconstruct
        compressed = []
        if system_msg:
            compressed.append(system_msg)
        compressed.extend(first_msgs)

        # Insert summary as a system-like message
        compressed.append({
            "role": "user",
            "content": f"[Context compressed - summary of {len(middle_msgs)} previous messages]\n\n{summary}\n\n[End of compressed context. Continue from here.]"
        })

        compressed.extend(last_msgs)

        # Log reduction
        old_tokens = estimate_messages_tokens(messages)
        new_tokens = estimate_messages_tokens(compressed)
        logger.info(
            f"[Compressor] Messages: {len(messages)} → {len(compressed)}, "
            f"Est. tokens: {old_tokens:,} → {new_tokens:,} "
            f"(saved ~{old_tokens - new_tokens:,})"
        )

        if self.compression_count >= 3:
            logger.warning(
                f"[Compressor] Session compressed {self.compression_count} times — "
                f"quality may degrade. Consider starting a new session."
            )

        return compressed

    def _summarize_messages(self, messages: list[dict[str, Any]]) -> str:
        """Create a structured summary of messages.

        This is a local summary (no LLM call) — fast but less intelligent.
        For LLM-powered summarization, the AgentLoop can call the LLM separately.
        """
        parts = []
        tool_calls_seen = set()
        key_decisions = []
        files_modified = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user" and isinstance(content, str) and content.strip():
                # Skip reflection prompts
                if content.startswith("Reflect on"):
                    continue
                parts.append(f"• User asked: {content[:200]}")

            elif role == "assistant":
                # Track tool calls
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        func = tc.get("function", {})
                        name = func.get("name", "")
                        args = func.get("arguments", "")
                        if isinstance(args, str):
                            try:
                                args_dict = json.loads(args)
                            except json.JSONDecodeError:
                                args_dict = {}
                        else:
                            args_dict = args if isinstance(args, dict) else {}

                        tool_calls_seen.add(name)

                        # Track file modifications
                        if name in ("write_file", "edit_file"):
                            path = args_dict.get("path", "")
                            if path:
                                files_modified.append(path)

                # Track text responses
                if isinstance(content, str) and content.strip() and not tool_calls:
                    key_decisions.append(content[:150])

            elif role == "tool":
                # Summarize tool results briefly
                name = msg.get("name", "")
                if isinstance(content, str) and len(content) > 200:
                    parts.append(f"• Tool {name}: [result {len(content)} chars]")

        summary_parts = []

        if tool_calls_seen:
            summary_parts.append(f"**Tools used:** {', '.join(sorted(tool_calls_seen))}")

        if files_modified:
            summary_parts.append(f"**Files modified:** {', '.join(files_modified[:10])}")

        if key_decisions:
            summary_parts.append("**Key responses:**")
            for d in key_decisions[:5]:
                summary_parts.append(f"  - {d}")

        if parts:
            summary_parts.append("**Conversation flow:**")
            # Keep first 5 and last 5 items
            if len(parts) > 10:
                summary_parts.extend(parts[:5])
                summary_parts.append(f"  ... ({len(parts) - 10} more exchanges) ...")
                summary_parts.extend(parts[-5:])
            else:
                summary_parts.extend(parts)

        return "\n".join(summary_parts) if summary_parts else "(No significant content to summarize)"


class SmartCompressor(ContextCompressor):
    """LLM-powered context compressor — uses a cheap model for intelligent summarization.

    Inspired by HuggingFace ml-intern's 170K compaction and Pi's context management.
    Falls back to mechanical summarization if LLM call fails.

    Args:
        cheap_model: Model to use for summarization (e.g. "deepseek-chat", "gpt-4o-mini").
        provider: LLM provider instance. If None, will be set later via set_provider().
        **kwargs: Passed to ContextCompressor.
    """

    def __init__(
        self,
        cheap_model: str = "deepseek-chat",
        provider: Any = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.cheap_model = cheap_model
        self._provider = provider
        self._smart_available = True  # disable after repeated failures

    def set_provider(self, provider: Any) -> None:
        """Set the LLM provider (called by AgentLoop after init)."""
        self._provider = provider

    def compress(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compress with LLM summarization, falling back to mechanical."""
        if len(messages) <= self.keep_first + self.keep_last + 2:
            logger.info("[SmartCompressor] Too few messages to compress, skipping")
            return messages

        self.compression_count += 1

        # Split messages
        system_msg = messages[0] if messages[0]["role"] == "system" else None
        start_idx = 1 if system_msg else 0
        first_end = start_idx + self.keep_first
        last_start = len(messages) - self.keep_last

        if first_end >= last_start:
            return messages

        first_msgs = messages[start_idx:first_end]
        middle_msgs = messages[first_end:last_start]
        last_msgs = messages[last_start:]

        # Try smart summarization first, fall back to mechanical
        if self._smart_available and self._provider:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're inside an async context — schedule coroutine
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        summary = pool.submit(
                            asyncio.run, self._smart_summarize(middle_msgs)
                        ).result(timeout=30)
                else:
                    summary = asyncio.run(self._smart_summarize(middle_msgs))
                logger.info(f"[SmartCompressor] LLM summarized {len(middle_msgs)} messages")
            except Exception as e:
                logger.warning(f"[SmartCompressor] LLM summarization failed: {e}, falling back")
                self._smart_fail_count = getattr(self, '_smart_fail_count', 0) + 1
                if self._smart_fail_count >= 3:
                    logger.warning("[SmartCompressor] Too many failures, disabling smart mode")
                    self._smart_available = False
                summary = self._summarize_messages(middle_msgs)
        else:
            summary = self._summarize_messages(middle_msgs)

        # Reconstruct
        compressed = []
        if system_msg:
            compressed.append(system_msg)
        compressed.extend(first_msgs)
        compressed.append({
            "role": "user",
            "content": (
                f"[Context compressed — summary of {len(middle_msgs)} previous messages]\n\n"
                f"{summary}\n\n"
                f"[End of compressed context. Continue from here.]"
            ),
        })
        compressed.extend(last_msgs)

        old_tokens = estimate_messages_tokens(messages)
        new_tokens = estimate_messages_tokens(compressed)
        logger.info(
            f"[SmartCompressor] Messages: {len(messages)} → {len(compressed)}, "
            f"Est. tokens: {old_tokens:,} → {new_tokens:,} "
            f"(saved ~{old_tokens - new_tokens:,})"
        )
        return compressed

    async def _smart_summarize(self, messages: list[dict[str, Any]]) -> str:
        """Use a cheap LLM to produce a high-quality summary."""
        # Format messages for the summarizer
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            if isinstance(content, str) and content.strip():
                # Truncate very long content
                display = content[:2000] + "..." if len(content) > 2000 else content
                formatted.append(f"[{role}] {display}")

            for tc in tool_calls:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    args = func.get("arguments", "")
                    if isinstance(args, str) and len(args) > 500:
                        args = args[:500] + "..."
                    formatted.append(f"[{role}] called {name}({args})")

        conversation_text = "\n".join(formatted)
        # Limit input to ~8K tokens worth
        if len(conversation_text) > 32000:
            conversation_text = conversation_text[:16000] + "\n...\n" + conversation_text[-16000:]

        summary_messages = [
            {
                "role": "system",
                "content": (
                    "You are a conversation summarizer. Produce a concise but complete summary. "
                    "You MUST preserve:\n"
                    "1. Key decisions and conclusions reached\n"
                    "2. File paths that were read, created, or modified\n"
                    "3. Important tool results (especially errors)\n"
                    "4. User requirements and preferences expressed\n"
                    "5. Code snippets or configurations that are still relevant\n"
                    "6. Any unresolved questions or pending tasks\n\n"
                    "Format as bullet points. Be factual, not verbose. Max 1000 words."
                ),
            },
            {
                "role": "user",
                "content": f"Summarize this conversation segment:\n\n{conversation_text}",
            },
        ]

        response = await self._provider.chat(
            messages=summary_messages,
            model=self.cheap_model,
            max_tokens=2000,
        )

        if hasattr(response, "content") and response.content:
            return response.content
        elif isinstance(response, dict):
            return response.get("content", "") or response.get("text", "")
        return str(response)
