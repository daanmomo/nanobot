"""LiteLLM provider implementation for multi-provider support."""

import json
import os
import platform
import re
import subprocess
import uuid
from typing import Any, AsyncIterator

import litellm
from litellm import acompletion
from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse, StreamChunk, ToolCallRequest
from nanobot.providers.registry import find_by_model, find_gateway


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.

    Supports OpenRouter, Anthropic, OpenAI, Gemini, MiniMax, and many other providers through
    a unified interface.  Provider-specific logic is driven by the registry
    (see providers/registry.py) — no if-elif chains needed here.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "deepseek/deepseek-chat",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
        no_proxy: bool = True,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.extra_headers = extra_headers or {}

        # Clear proxy environment variables to avoid connection issues
        # Common proxy vars that can interfere with API calls
        if no_proxy:
            for proxy_var in (
                "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
            ):
                if proxy_var in os.environ:
                    del os.environ[proxy_var]

        # Detect gateway / local deployment.
        # provider_name (from config key) is the primary signal;
        # api_key / api_base are fallback for auto-detection.
        self._gateway = find_gateway(provider_name, api_key, api_base)

        # Configure environment variables
        if api_key:
            self._setup_env(api_key, api_base, default_model)

        if api_base:
            litellm.api_base = api_base

        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
        # Drop unsupported parameters for providers (e.g., gpt-5 rejects some params)
        litellm.drop_params = True

    def _setup_env(self, api_key: str, api_base: str | None, model: str) -> None:
        """Set environment variables based on detected provider."""
        spec = self._gateway or find_by_model(model)
        if not spec:
            return

        if spec.name != "anthropic":
            for var in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_BASE"):
                if var in os.environ:
                    del os.environ[var]

        if self._gateway:
            os.environ[spec.env_key] = api_key
        else:
            os.environ.setdefault(spec.env_key, api_key)

        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key)
            resolved = resolved.replace("{api_base}", effective_base)
            if resolved:  # Only set when non-empty (e.g. skip ANTHROPIC_API_BASE when no custom base)
                os.environ.setdefault(env_name, resolved)

    @staticmethod
    def _is_proxy_error(error: Exception) -> bool:
        """Check if the error is caused by a proxy connection failure."""
        error_str = str(error).lower()
        proxy_indicators = [
            "connect call failed",
            "127.0.0.1:7890",
            "127.0.0.1:1080",
            "127.0.0.1:8080",
            "127.0.0.1:1087",
            "localhost:7890",
            "localhost:1080",
            "proxy",
            "cannot connect to host 127.0.0.1",
            "proxyerror",
            "proxies",
        ]
        return any(indicator in error_str for indicator in proxy_indicators)

    @staticmethod
    def _is_proxy_running() -> bool:
        """Check if a proxy process (Clash, etc.) is actually running and listening.

        Returns True if a proxy is alive on common ports (7890, 1080, 8080).
        """
        import socket
        proxy_ports = [7890, 1080, 8080, 1087]
        for port in proxy_ports:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return True
            except (ConnectionRefusedError, OSError, TimeoutError):
                continue
        return False

    @staticmethod
    def _disable_proxy() -> None:
        """Disable proxy settings: clear env vars and macOS system proxy."""
        # 1. Clear all proxy environment variables
        proxy_vars = [
            "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
            "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
        ]
        cleared = []
        for var in proxy_vars:
            if var in os.environ:
                del os.environ[var]
                cleared.append(var)
        if cleared:
            logger.info(f"[ProxyFix] Cleared env vars: {', '.join(cleared)}")

        # 2. Disable macOS system proxy (if on macOS)
        if platform.system() == "Darwin":
            try:
                # Get active network service
                result = subprocess.run(
                    ["networksetup", "-listallnetworkservices"],
                    capture_output=True, text=True, timeout=5,
                )
                services = [
                    line.strip() for line in result.stdout.strip().split("\n")
                    if line.strip() and not line.startswith("*")
                ]
                for service in services:
                    # Turn off HTTP proxy
                    subprocess.run(
                        ["networksetup", "-setwebproxystate", service, "off"],
                        capture_output=True, timeout=5,
                    )
                    # Turn off HTTPS proxy
                    subprocess.run(
                        ["networksetup", "-setsecurewebproxystate", service, "off"],
                        capture_output=True, timeout=5,
                    )
                    # Turn off SOCKS proxy
                    subprocess.run(
                        ["networksetup", "-setsocksfirewallproxystate", service, "off"],
                        capture_output=True, timeout=5,
                    )
                logger.info(f"[ProxyFix] Disabled macOS system proxy for: {', '.join(services)}")
            except Exception as e:
                logger.warning(f"[ProxyFix] Failed to disable macOS system proxy: {e}")

    def _extract_text_from_blocks(self, content: list) -> str:
        """Extract text from Anthropic-style content blocks.

        Handles both dict-style blocks and object-style blocks (Pydantic models).
        """
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            elif hasattr(block, "type") and hasattr(block, "text"):
                if block.type == "text":
                    text_parts.append(block.text or "")
            elif isinstance(block, str):
                text_parts.append(block)
        return "".join(text_parts) if text_parts else ""

    def _parse_xml_tool_calls(self, content: str) -> tuple[list[ToolCallRequest], str]:
        """Parse XML-formatted tool calls from content.

        Some models (DeepSeek, Qwen, Hunyuan, etc.) return tool calls as XML text
        instead of native tool_calls. This method extracts and parses them.

        Args:
            content: Response content that may contain <function_calls> XML.

        Returns:
            Tuple of (list of ToolCallRequest, remaining content without XML).
        """
        tool_calls = []
        remaining_content = content

        # Match <function_calls>...</function_calls> block
        fc_pattern = r"<function_calls>(.*?)</function_calls>"
        fc_match = re.search(fc_pattern, content, re.DOTALL)

        if not fc_match:
            return tool_calls, content

        fc_block = fc_match.group(1)

        # Remove the function_calls block from content
        remaining_content = re.sub(fc_pattern, "", content, flags=re.DOTALL).strip()

        # Parse each <invoke> block
        invoke_pattern = r'<invoke\s+name="([^"]+)">(.*?)</invoke>'
        for invoke_match in re.finditer(invoke_pattern, fc_block, re.DOTALL):
            tool_name = invoke_match.group(1)
            params_block = invoke_match.group(2)

            # Parse parameters
            args = {}
            # Format: <parameter name="key" string="true">value</parameter>
            # or: <parameter name="key">value</parameter>
            param_pattern = r'<parameter\s+name="([^"]+)"(?:\s+[^>]*)?>([^<]*)</parameter>'
            for param_match in re.finditer(param_pattern, params_block):
                param_name = param_match.group(1)
                param_value = param_match.group(2).strip()

                # Try to parse as JSON for non-string values
                try:
                    args[param_name] = json.loads(param_value)
                except (json.JSONDecodeError, ValueError):
                    args[param_name] = param_value

            tool_calls.append(ToolCallRequest(
                id=f"xml_{uuid.uuid4().hex[:8]}",
                name=tool_name,
                arguments=args,
            ))

        return tool_calls, remaining_content

    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying provider/gateway prefixes."""
        if self._gateway:
            # Gateway mode: apply gateway prefix, skip provider-specific prefixes
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix and not model.startswith(f"{prefix}/"):
                model = f"{prefix}/{model}"
            return model

        # Standard mode: auto-prefix for known providers
        spec = find_by_model(model)
        if spec and spec.litellm_prefix:
            if not any(model.startswith(s) for s in spec.skip_prefixes):
                model = f"{spec.litellm_prefix}/{model}"

        return model

    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        """Apply model-specific parameter overrides from the registry."""
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with content and/or tool calls.
        """
        model = self._resolve_model(model or self.default_model)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Apply model-specific overrides (e.g. kimi-k2.5 temperature)
        self._apply_model_overrides(model, kwargs)

        # Pass api_key directly — more reliable than env vars alone
        if self.api_key:
            kwargs["api_key"] = self.api_key

        # Pass api_base for custom endpoints
        if self.api_base:
            kwargs["api_base"] = self.api_base

        # Pass extra headers (e.g. APP-Code for AiHubMix)
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            if self._is_proxy_error(e):
                proxy_alive = self._is_proxy_running()
                if proxy_alive:
                    # Proxy is running but had a hiccup — just retry without disabling
                    logger.warning(f"[ProxyFix] Proxy error but proxy IS running: {e}")
                    logger.info("[ProxyFix] Retrying (proxy kept alive)...")
                else:
                    # Proxy is NOT running — disable proxy settings and retry direct
                    logger.warning(f"[ProxyFix] Proxy error and proxy NOT running: {e}")
                    logger.info("[ProxyFix] Auto-disabling proxy and retrying direct...")
                    self._disable_proxy()
                try:
                    response = await acompletion(**kwargs)
                    logger.info("[ProxyFix] Retry succeeded!")
                    return self._parse_response(response)
                except Exception as retry_e:
                    return LLMResponse(
                        content=f"Error calling LLM (retry failed): {str(retry_e)}",
                        finish_reason="error",
                    )
            # Return error as content for graceful handling
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}

                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        reasoning_content = getattr(message, "reasoning_content", None)

        # Handle Anthropic-style content format [{'type': 'text', 'text': '...'}]
        content = message.content
        if isinstance(content, list):
            content = self._extract_text_from_blocks(content)

        # Parse XML-formatted tool calls if no native tool_calls found
        if not tool_calls and content and "<function_calls>" in content:
            tool_calls, content = self._parse_xml_tool_calls(content)
            # Set content to None if it's empty after removing XML
            if not content:
                content = None

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content,
        )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[StreamChunk]:
        """
        Send a streaming chat completion request via LiteLLM.

        Yields StreamChunk objects with incremental content, reasoning, or tool calls.
        """
        model = self._resolve_model(model or self.default_model)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        # Apply model-specific overrides
        self._apply_model_overrides(model, kwargs)

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await acompletion(**kwargs)
        except Exception as e:
            if self._is_proxy_error(e):
                proxy_alive = self._is_proxy_running()
                if proxy_alive:
                    logger.warning(f"[ProxyFix] Stream proxy error but proxy IS running: {e}")
                    logger.info("[ProxyFix] Retrying stream (proxy kept alive)...")
                else:
                    logger.warning(f"[ProxyFix] Stream proxy error and proxy NOT running: {e}")
                    logger.info("[ProxyFix] Auto-disabling proxy and retrying stream direct...")
                    self._disable_proxy()
                try:
                    response = await acompletion(**kwargs)
                    logger.info("[ProxyFix] Stream retry succeeded!")
                except Exception as retry_e:
                    yield StreamChunk(
                        content=f"Error calling LLM (retry failed): {str(retry_e)}",
                        finish_reason="error",
                    )
                    return
            else:
                yield StreamChunk(
                    content=f"Error calling LLM: {str(e)}",
                    finish_reason="error",
                )
                return

        try:
            # Track accumulated tool calls for assembly
            tool_calls_acc: dict[int, dict[str, Any]] = {}

            async for chunk in response:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                # Extract content
                content = getattr(delta, "content", None)
                # Handle Anthropic-style content format in streaming
                if isinstance(content, list):
                    content = self._extract_text_from_blocks(content) or None

                # Extract reasoning_content (DeepSeek-R1, Kimi etc.)
                reasoning = getattr(delta, "reasoning_content", None)

                # Extract tool call deltas
                tc_deltas = []
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index if hasattr(tc, "index") else 0
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": "",
                                "name": "",
                                "arguments": "",
                            }
                        if hasattr(tc, "id") and tc.id:
                            tool_calls_acc[idx]["id"] = tc.id
                        if hasattr(tc, "function") and tc.function:
                            if tc.function.name:
                                tool_calls_acc[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_acc[idx]["arguments"] += tc.function.arguments

                        tc_deltas.append({
                            "index": idx,
                            "id": getattr(tc, "id", None),
                            "name": tc.function.name if hasattr(tc, "function") and tc.function else None,
                            "arguments_delta": tc.function.arguments if hasattr(tc, "function") and tc.function else None,
                        })

                # Extract usage from final chunk
                usage = {}
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }

                yield StreamChunk(
                    content=content,
                    reasoning_content=reasoning,
                    tool_calls_delta=tc_deltas,
                    finish_reason=finish_reason,
                    usage=usage,
                )

        except Exception as e:
            yield StreamChunk(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )

    def assemble_stream_response(
        self,
        chunks: list[StreamChunk],
    ) -> LLMResponse:
        """
        Assemble collected stream chunks into a final LLMResponse.

        Args:
            chunks: List of StreamChunk objects collected during streaming.

        Returns:
            LLMResponse with assembled content and tool calls.
        """
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_acc: dict[int, dict[str, Any]] = {}
        finish_reason = "stop"
        usage: dict[str, int] = {}

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

        # Parse tool calls
        tool_calls: list[ToolCallRequest] = []
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

        content = "".join(content_parts) or None

        # Parse XML-formatted tool calls if no native tool_calls found
        if not tool_calls and content and "<function_calls>" in content:
            tool_calls, content = self._parse_xml_tool_calls(content)
            if not content:
                content = None

        return LLMResponse(
            content=content,
            reasoning_content="".join(reasoning_parts) or None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )
