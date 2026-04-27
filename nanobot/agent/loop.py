"""Agent loop: the core processing engine.

v3 — Enhanced with Hermes-inspired patterns:
  1. ErrorClassifier + structured retry/recovery
  2. ContextCompressor + automatic context management
  3. Parallel tool execution for independent tools
  4. Redact — sensitive info masking in tool output & logs
  5. Smart Router — cheap model for simple messages
  6. Trajectory — conversation saving for analysis & training
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.config.schema import ExecToolConfig, TencentSearchConfig
    from nanobot.cron.service import CronService

from typing import Awaitable, Callable

from nanobot.agent.compressor import ContextCompressor
from nanobot.agent.doom_loop import LEVEL_BREAK, LEVEL_OK, DoomLoopDetector
from nanobot.agent.context import ContextBuilder
from nanobot.agent.error_classifier import ClassifiedError, FailoverReason, classify_api_error
from nanobot.agent.parallel import execute_parallel, should_parallelize
from nanobot.agent.router import choose_model
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tool_router import select_tool_names
from nanobot.agent.trajectory import save_trajectory
from nanobot.utils.redact import redact, redact_tool_output
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.web import (
    DuckDuckGoSearchTool,
    TencentSearchTool,
    ThinkTool,
    WebFetchTool,
    WebSearchTool,
)
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse, StreamChunk, ToolCallRequest
from nanobot.session.manager import SessionManager

# 流式回调类型: (channel, chat_id, content, is_final) -> bool (True 表示已发送最终消息)
StreamCallback = Callable[[str, str, str, bool], Awaitable[bool]]

# Retry constants
_MAX_RETRIES = 3
_BASE_RETRY_DELAY = 1.0

# Optional tools - import at module level, register if available
_OPTIONAL_TOOL_MODULES: list[tuple[str, list]] = []
for _module, _attr in [
    ("nanobot.agent.tools.stock", "STOCK_TOOLS"),
    ("nanobot.agent.tools.usstock", "USSTOCK_TOOLS"),
    ("nanobot.agent.tools.fund", "FUND_TOOLS"),
    ("nanobot.agent.tools.forex", "FOREX_TOOLS"),
    ("nanobot.agent.tools.news", "NEWS_TOOLS"),
    ("nanobot.agent.tools.browser", "BROWSER_TOOLS"),
    ("nanobot.agent.tools.openbb", "OPENBB_TOOLS"),
    ("nanobot.agent.tools.screenshot", "SCREENSHOT_TOOLS"),
]:
    try:
        _mod = __import__(_module, fromlist=[_attr])
        _OPTIONAL_TOOL_MODULES.append((_module.split(".")[-1], getattr(_mod, _attr)))
    except ImportError:
        pass


class AgentLoop:
    """
    The agent loop is the core processing engine.

    Enhanced with:
    - Structured error classification and recovery (Hermes-inspired)
    - Automatic context compression when token usage is high
    - Parallel tool execution for independent read-only tools
    """

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 50,
        max_tokens: int = 8192,
        max_context_tokens: int = 200000,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        tencent_config: "TencentSearchConfig | None" = None,
        cron_service: "CronService | None" = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig, TencentSearchConfig
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.tencent_config = tencent_config or TencentSearchConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace

        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        # Context compressor (Hermes-inspired)
        self.compressor = ContextCompressor(
            max_context_tokens=max_context_tokens,
            compress_threshold=0.5,
            keep_first=2,
            keep_last=10,
        )

        # Smart model routing (Hermes-inspired)
        # Set cheap_model via NANOBOT_CHEAP_MODEL env var or config
        self.cheap_model = os.environ.get("NANOBOT_CHEAP_MODEL", None)
        # Trajectory saving (Hermes-inspired)
        self.save_trajectories = os.environ.get("NANOBOT_SAVE_TRAJECTORIES", "true").lower() not in ("0", "false", "no")

        self._running = False
        # 流式输出回调 (channel, chat_id, content, is_final) -> None
        self._stream_callback: StreamCallback | None = None
        # 当前流式输出的上下文
        self._current_stream_ctx: dict | None = None

    def set_stream_callback(self, callback: StreamCallback) -> None:
        """设置流式输出回调函数。"""
        self._stream_callback = callback
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools (restrict to workspace if configured)
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(allowed_dir=allowed_dir))
        self.tools.register(EditFileTool(allowed_dir=allowed_dir))
        self.tools.register(ListDirTool(allowed_dir=allowed_dir))

        # Shell tool
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
        ))

        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(DuckDuckGoSearchTool())
        self.tools.register(TencentSearchTool(
            secret_id=self.tencent_config.secret_id,
            secret_key=self.tencent_config.secret_key,
            endpoint=self.tencent_config.endpoint,
        ))
        self.tools.register(WebFetchTool())
        self.tools.register(ThinkTool())

        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)

        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)

        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

        # Register optional tools (stock, usstock, fund, forex, news, browser)
        for _name, tool_classes in _OPTIONAL_TOOL_MODULES:
            for tool_cls in tool_classes:
                self.tools.register(tool_cls())

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")

        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )

                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """Process a single inbound message."""
        # Handle system messages (subagent announces)
        if msg.channel == "system":
            return await self._process_system_message(msg)

        # Log user input
        logger.info(f"[User:{msg.channel}:{msg.sender_id}] {msg.content}")

        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)

        # Update tool contexts
        self._update_tool_contexts(msg.channel, msg.chat_id)

        # Build initial messages
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )

        # 设置流式输出上下文
        self._current_stream_ctx = {
            "channel": msg.channel,
            "chat_id": msg.chat_id,
            "started": False,
        }

        # Smart model routing (Hermes-inspired)
        turn_model, routing_reason = choose_model(msg.content, self.model, self.cheap_model)
        if routing_reason:
            logger.info(f"[Router] Routed to {turn_model} (reason: {routing_reason})")

        # Track timing for trajectory
        _start_time = time.monotonic()

        # Run the agent loop with error recovery
        final_content = await self._run_agent_loop(messages, model_override=turn_model)

        # Log final response
        logger.info(f"[Assistant] {final_content}")

        # 发送最终的流式回调
        stream_handled = False
        if self._stream_callback and self._current_stream_ctx:
            ctx = self._current_stream_ctx
            try:
                stream_handled = await self._stream_callback(ctx["channel"], ctx["chat_id"], final_content, True)
            except Exception as e:
                logger.warning(f"Final stream callback error: {e}")

        # 清理流式上下文
        self._current_stream_ctx = None

        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        if stream_handled:
            return None

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata=msg.metadata or {},
        )

    def _update_tool_contexts(self, channel: str, chat_id: str) -> None:
        """Update tool contexts for the current message."""
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(channel, chat_id)

        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(channel, chat_id)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(channel, chat_id)

    async def _run_agent_loop(self, messages: list[dict], model_override: str | None = None) -> str:
        """Run the main agent loop with error recovery and context compression.

        Returns:
            Final response content string.
        """
        iteration = 0
        final_content = None

        while iteration < self.max_iterations:
            iteration += 1

            # ── Context compression check ──
            if self.compressor.should_compress(messages):
                logger.info(f"[AgentLoop] Compressing context at iteration {iteration}")
                messages = self.compressor.compress(messages)

            # ── Dynamic tool selection (Pi-inspired) ──
            selected_names = select_tool_names(self.tools.tool_names, messages)
            all_count = len(self.tools)
            sel_count = len(selected_names)
            if sel_count < all_count:
                filtered_defs = self.tools.get_definitions_filtered(selected_names)
                logger.info(
                    f"[ToolRouter] Selected {sel_count}/{all_count} tools "
                    f"(saved {all_count - sel_count} tool defs)"
                )
            else:
                filtered_defs = ...  # sentinel: use all tools
                logger.debug(f"[ToolRouter] Using all {all_count} tools")

            # ── Call LLM with error recovery ──
            response = await self._call_llm_with_recovery(messages, tools_override=filtered_defs, model_override=model_override)

            if response is None:
                # Unrecoverable error
                final_content = "I encountered an error I couldn't recover from. Please try again."
                break

            # ── Handle tool calls ──
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )

                # Execute tools (parallel if safe, sequential otherwise)
                messages = await self._execute_tools(messages, response.tool_calls)

                # Interleaved CoT
                messages.append({"role": "user", "content": "Reflect on the results and decide next steps."})

                # Update compressor with usage info
                if response.usage:
                    self.compressor.should_compress(messages, usage=response.usage)
            else:
                final_content = response.content
                break

        if final_content is None:
            # Max iterations reached — force summary
            logger.info("[AgentLoop] Max iterations reached, forcing final summary")
            messages.append({
                "role": "user",
                "content": "You have reached the maximum number of iterations. "
                           "Summarize what you have done and provide your final response to the user.",
            })
            summary_response = await self._call_llm_with_recovery(messages, tools_override=None, model_override=model_override)
            if summary_response and summary_response.content:
                final_content = summary_response.content
            else:
                final_content = "I've completed processing but have no response to give."

        return final_content

    async def _call_llm_with_recovery(
        self,
        messages: list[dict],
        tools_override: list[dict] | None = ...,
        model_override: str | None = None,
    ) -> LLMResponse | None:
        """Call LLM with structured error recovery.

        Implements Hermes-inspired error classification and recovery:
        - Rate limit → exponential backoff + retry
        - Context overflow → compress + retry
        - Server error → retry with backoff
        - Auth/billing → abort (not recoverable without new credentials)
        - Timeout → retry with increased timeout

        Args:
            messages: Conversation messages.
            tools_override: Tool definitions override.

        Returns:
            LLMResponse on success, None if unrecoverable.
        """
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await self._call_llm_stream(messages, tools_override, model_override=model_override)

            except Exception as e:
                last_error = e

                # Classify the error
                classified = classify_api_error(
                    e,
                    approx_tokens=self.compressor.last_token_estimate,
                    context_length=self.compressor.max_context_tokens,
                    num_messages=len(messages),
                )

                logger.warning(
                    f"[Recovery] Attempt {attempt + 1}/{_MAX_RETRIES + 1} failed: "
                    f"reason={classified.reason.value}, "
                    f"status={classified.status_code}, "
                    f"retryable={classified.retryable}, "
                    f"msg={classified.message[:100]}"
                )

                # ── Non-retryable errors → abort immediately ──
                if not classified.retryable:
                    logger.error(
                        f"[Recovery] Non-retryable error: {classified.reason.value} — "
                        f"{classified.message[:200]}"
                    )
                    return None

                # ── Last attempt → give up ──
                if attempt >= _MAX_RETRIES:
                    logger.error(
                        f"[Recovery] Max retries ({_MAX_RETRIES}) exhausted for "
                        f"{classified.reason.value}"
                    )
                    return None

                # ── Context overflow → compress and retry ──
                if classified.should_compress:
                    logger.info("[Recovery] Compressing context due to overflow")
                    messages = self.compressor.compress(messages)
                    # No delay needed — just retry with smaller context
                    continue

                # ── Retryable errors → backoff and retry ──
                delay = classified.retry_delay * (2 ** attempt)  # Exponential backoff
                logger.info(f"[Recovery] Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

        # Should not reach here, but just in case
        logger.error(f"[Recovery] Unexpected fallthrough, last error: {last_error}")
        return None

    async def _execute_tools(
        self,
        messages: list[dict],
        tool_calls: list[ToolCallRequest],
    ) -> list[dict]:
        """Execute tool calls, using parallel execution when safe.

        Args:
            messages: Current message list (will be modified in place).
            tool_calls: Tool calls from the LLM response.

        Returns:
            Updated message list with tool results appended.
        """
        # Build tool call info for parallel check
        tc_infos = [
            {
                "id": tc.id,
                "name": tc.name,
                "arguments": tc.arguments,
            }
            for tc in tool_calls
        ]

        if len(tool_calls) > 1 and should_parallelize(tc_infos):
            # ── Parallel execution ──
            logger.info(f"[Tools] Executing {len(tool_calls)} tools in parallel")
            results = await execute_parallel(
                tc_infos,
                executor=self.tools.execute,
            )
            for tc_id, tc_name, result in results:
                args_str = json.dumps(
                    next((tc.arguments for tc in tool_calls if tc.id == tc_id), {}),
                    ensure_ascii=False,
                )
                logger.info(f"[Tool] {tc_name}({args_str[:200]})")
                messages = self.context.add_tool_result(messages, tc_id, tc_name, result)
        else:
            # ── Sequential execution ──
            for tool_call in tool_calls:
                args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                logger.info(f"[Tool] {tool_call.name}({args_str[:200]})")
                result = await self.tools.execute(tool_call.name, tool_call.arguments)
                messages = self.context.add_tool_result(
                    messages, tool_call.id, tool_call.name, result
                )

        return messages

    async def _call_llm_stream(
        self, messages: list[dict], tools_override: list[dict] | None = ...,
        model_override: str | None = None,
    ) -> LLMResponse:
        """Call LLM with streaming and log reasoning/content in real-time.

        Args:
            messages: The conversation messages.
            tools_override: Explicit tool definitions to pass. Use ``None`` to
                disable tools (force text-only response). Omit (sentinel ``...``)
                to use the default ``self.tools.get_definitions()``.

        Returns:
            Assembled LLMResponse from stream chunks.
        """
        from nanobot.providers.litellm_provider import LiteLLMProvider

        tool_defs = self.tools.get_definitions() if tools_override is ... else tools_override

        chunks: list[StreamChunk] = []
        reasoning_buffer = ""
        content_buffer = ""
        full_content = ""

        async for chunk in self.provider.chat_stream(
            messages=messages,
            tools=tool_defs,
            model=model_override or self.model,
            max_tokens=self.max_tokens,
        ):
            chunks.append(chunk)

            # Log reasoning (thinking) in real-time
            if chunk.reasoning_content:
                reasoning_buffer += chunk.reasoning_content
                while "\n" in reasoning_buffer:
                    line, reasoning_buffer = reasoning_buffer.split("\n", 1)
                    if line.strip():
                        logger.info(f"[Thinking] {line}")

            # Log content in real-time and trigger stream callback
            if chunk.content:
                content_buffer += chunk.content
                full_content += chunk.content

                if self._stream_callback and self._current_stream_ctx:
                    ctx = self._current_stream_ctx
                    try:
                        await self._stream_callback(
                            ctx["channel"], ctx["chat_id"], full_content, False
                        )
                    except Exception as e:
                        logger.warning(f"Stream callback error: {e}")

                while "\n" in content_buffer:
                    line, content_buffer = content_buffer.split("\n", 1)
                    if line.strip():
                        logger.info(f"[Stream] {line}")

        # Log remaining buffers
        if reasoning_buffer.strip():
            logger.info(f"[Thinking] {reasoning_buffer}")
        if content_buffer.strip():
            logger.info(f"[Stream] {content_buffer}")

        # Assemble final response
        if isinstance(self.provider, LiteLLMProvider):
            response = self.provider.assemble_stream_response(chunks)
        else:
            response = self._assemble_chunks(chunks)

        # Log model output
        logger.info(f"[LLM Response] finish_reason={response.finish_reason}")
        if response.usage:
            logger.info(
                f"[LLM Usage] prompt_tokens={response.usage.get('prompt_tokens', 0)}, "
                f"completion_tokens={response.usage.get('completion_tokens', 0)}, "
                f"total_tokens={response.usage.get('total_tokens', 0)}"
            )
            # Update compressor with actual token usage
            self.compressor.last_token_estimate = response.usage.get('prompt_tokens', 0)
        if response.reasoning_content:
            logger.info(f"[LLM Reasoning] {response.reasoning_content}")
        if response.content:
            logger.info(f"[LLM Content] {response.content}")
        if response.tool_calls:
            for tc in response.tool_calls:
                args_json = json.dumps(tc.arguments, ensure_ascii=False, indent=2)
                logger.info(f"[LLM ToolCall] id={tc.id}, name={tc.name}, arguments=\n{args_json}")

        return response

    def _assemble_chunks(self, chunks: list[StreamChunk]) -> LLMResponse:
        """Fallback chunk assembly for non-LiteLLM providers."""
        content_parts = []
        reasoning_parts = []
        tool_calls_acc: dict[int, dict] = {}
        finish_reason = "stop"
        usage = {}

        for chunk in chunks:
            if chunk.content:
                content_parts.append(chunk.content)
            if chunk.reasoning_content:
                reasoning_parts.append(chunk.reasoning_content)
            if chunk.finish_reason:
                finish_reason = chunk.finish_reason
            if chunk.usage:
                usage = chunk.usage

            for tc_delta in chunk.tool_calls_delta:
                idx = tc_delta.get("index", 0)
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                if tc_delta.get("id"):
                    tool_calls_acc[idx]["id"] = tc_delta["id"]
                if tc_delta.get("name"):
                    tool_calls_acc[idx]["name"] = tc_delta["name"]
                if tc_delta.get("arguments_delta"):
                    tool_calls_acc[idx]["arguments"] += tc_delta["arguments_delta"]

        tool_calls = []
        for idx in sorted(tool_calls_acc.keys()):
            tc = tool_calls_acc[idx]
            if tc["id"] and tc["name"]:
                args = tc["arguments"]
                try:
                    args = json.loads(args) if args else {}
                except json.JSONDecodeError:
                    args = {"raw": args}
                tool_calls.append(ToolCallRequest(
                    id=tc["id"],
                    name=tc["name"],
                    arguments=args,
                ))

        return LLMResponse(
            content="".join(content_parts) or None,
            reasoning_content="".join(reasoning_parts) or None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """Process a system message (e.g., subagent announce)."""
        logger.info(f"[System:{msg.sender_id}] {msg.content}")

        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            origin_channel = "cli"
            origin_chat_id = msg.chat_id

        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)

        # Update tool contexts
        self._update_tool_contexts(origin_channel, origin_chat_id)

        # Build messages
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )

        # Run agent loop with full error recovery
        final_content = await self._run_agent_loop(messages)

        logger.info(f"[Assistant] {final_content}")

        # Save to session
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
    ) -> str:
        """Process a message directly (for CLI or cron usage)."""
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content
        )

        response = await self._process_message(msg)
        return response.content if response else ""
