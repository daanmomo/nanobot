"""Web tools: search, fetch, and research utilities.

Provides:
- WebSearchTool: Brave Search API
- TencentSearchTool: Tencent Search API (for Chinese content)
- WebFetchTool: Fetch and extract content from URLs
- ThinkTool: Strategic reflection for research workflows
"""

import base64
import hashlib
import hmac
import html
import json
import os
import random
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from nanobot.agent.tools.base import Tool

# Shared constants
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"
MAX_REDIRECTS = 5


def _strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _validate_url(url: str) -> tuple[bool, str]:
    """Validate URL: must be http(s) with valid domain."""
    try:
        p = urlparse(url)
        if p.scheme not in ('http', 'https'):
            return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
        if not p.netloc:
            return False, "Missing domain"
        return True, ""
    except Exception as e:
        return False, str(e)


# ==================== Tencent API Utilities ====================


def _tencent_get_string_to_sign(method: str, endpoint: str, params: dict) -> str:
    """Get string for Tencent API signature."""
    s = method + endpoint + "/?"
    query_str = "&".join("%s=%s" % (k, params[k]) for k in sorted(params))
    return s + query_str


def _tencent_sign_str(key: str, s: str, method) -> str:
    """Sign string for Tencent API."""
    if not key:
        raise ValueError("Signing key cannot be empty")
    hmac_str = hmac.new(key.encode("utf8"), s.encode("utf8"), method).digest()
    return base64.b64encode(hmac_str).decode("utf8")


def _tencent_generate_params(query: str, secret_id: str) -> dict:
    """Generate Tencent Search API request parameters."""
    return {
        'Action': 'SearchPro',
        'Query': query,
        'Mode': 0,
        'Cnt': 10,
        'SecretId': secret_id,
        'Timestamp': int(time.time()),
        'Nonce': random.randint(1, 1000000),
        'Version': '2025-05-08',
        'SignatureMethod': 'HmacSHA256'
    }


# ==================== Web Search Tools ====================


class WebSearchTool(Tool):
    """Search the web using Brave Search API."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web using Brave Search API. Returns titles, URLs, and snippets."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "count": {
                    "type": "integer",
                    "description": "Number of results (1-10)",
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": ["query"]
        }

    def __init__(self, api_key: str | None = None, max_results: int = 5):
        self.api_key = api_key or os.environ.get("BRAVE_API_KEY", "")
        self.max_results = max_results

    async def execute(self, query: str, count: int | None = None, **kwargs: Any) -> str:
        if not self.api_key:
            return "Error: BRAVE_API_KEY not configured"

        try:
            n = min(max(count or self.max_results, 1), 10)
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": n},
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": self.api_key
                    },
                    timeout=10.0
                )
                r.raise_for_status()

            results = r.json().get("web", {}).get("results", [])
            if not results:
                return f"No results for: {query}"

            lines = [f"Results for: {query}\n"]
            for i, item in enumerate(results[:n], 1):
                lines.append(f"{i}. {item.get('title', '')}\n   {item.get('url', '')}")
                if desc := item.get("description"):
                    lines.append(f"   {desc}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"


class TencentSearchTool(Tool):
    """Search the web using Tencent Search API (better for Chinese content)."""

    @property
    def name(self) -> str:
        return "tencent_search"

    @property
    def description(self) -> str:
        return """使用腾讯搜索 API 搜索网络信息（适合中文内容）。
Returns search results with titles, URLs, snippets and dates."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (搜索查询)"
                },
            },
            "required": ["query"]
        }

    def __init__(
        self,
        secret_id: str | None = None,
        secret_key: str | None = None,
        endpoint: str = "wsa.tencentcloudapi.com"
    ):
        self.secret_id = secret_id or os.environ.get("TENCENT_SECRET_ID", "")
        self.secret_key = secret_key or os.environ.get("TENCENT_SECRET_KEY", "")
        self.endpoint = endpoint

    async def execute(self, query: str, **kwargs: Any) -> str:
        if not self.secret_id:
            return json.dumps({"error": "TENCENT_SECRET_ID not configured"})
        if not self.secret_key:
            return json.dumps({"error": "TENCENT_SECRET_KEY not configured"})

        try:
            # Generate request parameters
            data = _tencent_generate_params(query, self.secret_id)

            # Generate signature
            s = _tencent_get_string_to_sign("POST", self.endpoint, data)
            signature = _tencent_sign_str(self.secret_key, s, hashlib.sha256)
            data["Signature"] = signature

            # Send request
            url = "https://" + self.endpoint
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, data=data, headers=headers)
                resp.raise_for_status()

            response_json = resp.json()
            response_data = response_json.get("Response", {})

            # Check for errors
            if isinstance(response_data, dict) and "Error" in response_data:
                return json.dumps({
                    "error": f"Tencent API error: {response_data['Error']}"
                }, ensure_ascii=False)

            # Parse results
            pages = response_data.get("Pages", [])
            if not pages:
                return json.dumps({
                    "query": query,
                    "count": 0,
                    "results": [],
                    "message": "No results found"
                }, ensure_ascii=False)

            results = []
            for idx, page in enumerate(pages[:10], 1):
                if isinstance(page, str):
                    try:
                        page = json.loads(page)
                    except json.JSONDecodeError:
                        continue

                if isinstance(page, dict):
                    results.append({
                        "index": idx,
                        "title": page.get('title', ''),
                        "url": page.get('url', ''),
                        "snippet": page.get('passage', page.get('content', '')),
                        "date": page.get('date', '')
                    })

            return json.dumps({
                "query": query,
                "count": len(results),
                "results": results
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e), "query": query}, ensure_ascii=False)


# ==================== Web Fetch Tool ====================


class WebFetchTool(Tool):
    """Fetch and extract content from a URL."""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch URL and extract readable content (HTML → markdown/text)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "extractMode": {
                    "type": "string",
                    "enum": ["markdown", "text"],
                    "description": "Output format (default: markdown)"
                },
                "maxChars": {
                    "type": "integer",
                    "minimum": 100,
                    "description": "Maximum characters to return"
                }
            },
            "required": ["url"]
        }

    def __init__(self, max_chars: int = 50000):
        self.max_chars = max_chars

    async def execute(
        self,
        url: str,
        extract_mode: str = "markdown",
        max_chars: int | None = None,
        **kwargs: Any
    ) -> str:
        # Support both camelCase (from JSON schema) and snake_case parameter names
        extract_mode = kwargs.get("extractMode", extract_mode)
        max_chars = kwargs.get("maxChars", max_chars) or self.max_chars

        # Validate URL
        is_valid, error_msg = _validate_url(url)
        if not is_valid:
            return json.dumps({"error": f"URL validation failed: {error_msg}", "url": url})

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=MAX_REDIRECTS,
                timeout=30.0
            ) as client:
                r = await client.get(url, headers={"User-Agent": USER_AGENT})
                r.raise_for_status()

            ctype = r.headers.get("content-type", "")

            # JSON
            if "application/json" in ctype:
                text, extractor = json.dumps(r.json(), indent=2), "json"
            # HTML
            elif "text/html" in ctype or r.text[:256].lower().startswith(("<!doctype", "<html")):
                text, extractor = self._extract_html(r.text, extract_mode)
            else:
                text, extractor = r.text, "raw"

            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]

            return json.dumps({
                "url": url,
                "finalUrl": str(r.url),
                "status": r.status_code,
                "extractor": extractor,
                "truncated": truncated,
                "length": len(text),
                "text": text
            })
        except Exception as e:
            return json.dumps({"error": str(e), "url": url})

    def _extract_html(self, html_content: str, mode: str) -> tuple[str, str]:
        """Extract content from HTML."""
        # Try markdownify first (better quality)
        try:
            from markdownify import markdownify
            if mode == "markdown":
                text = markdownify(html_content, heading_style="ATX", strip=['script', 'style'])
                return _normalize(text), "markdownify"
        except ImportError:
            pass

        # Fallback to readability
        try:
            from readability import Document
            doc = Document(html_content)
            if mode == "markdown":
                content = self._to_markdown(doc.summary())
            else:
                content = _strip_tags(doc.summary())
            text = f"# {doc.title()}\n\n{content}" if doc.title() else content
            return text, "readability"
        except ImportError:
            pass

        # Final fallback: basic extraction
        if mode == "markdown":
            return self._to_markdown(html_content), "basic"
        return _strip_tags(html_content), "basic"

    def _to_markdown(self, html_content: str) -> str:
        """Convert HTML to markdown (basic fallback)."""
        text = re.sub(
            r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            lambda m: f'[{_strip_tags(m[2])}]({m[1]})', html_content, flags=re.I
        )
        text = re.sub(
            r'<h([1-6])[^>]*>([\s\S]*?)</h\1>',
            lambda m: f'\n{"#" * int(m[1])} {_strip_tags(m[2])}\n', text, flags=re.I
        )
        text = re.sub(
            r'<li[^>]*>([\s\S]*?)</li>',
            lambda m: f'\n- {_strip_tags(m[1])}', text, flags=re.I
        )
        text = re.sub(r'</(p|div|section|article)>', '\n\n', text, flags=re.I)
        text = re.sub(r'<(br|hr)\s*/?>', '\n', text, flags=re.I)
        return _normalize(_strip_tags(text))


# ==================== Think Tool ====================


class ThinkTool(Tool):
    """Strategic reflection tool for research workflows.

    Use after each search to analyze results and plan next steps.
    Creates an intentional pause for quality decision-making.
    """

    @property
    def name(self) -> str:
        return "think"

    @property
    def description(self) -> str:
        return """用于研究进度和决策制定的策略反思工具。

何时使用：
- 收到搜索结果后：分析找到了什么关键信息
- 决定下一步之前：评估是否有足够的信息
- 评估研究空白时：明确还缺少什么具体信息
- 结束研究之前：确认能否提供完整的答案

反思应涉及：
1. 当前发现的分析 - 收集了什么具体信息？
2. 空白评估 - 还缺少什么关键信息？
3. 质量评估 - 有足够的证据/示例吗？
4. 策略决策 - 应该继续搜索还是提供答案？"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "reflection": {
                    "type": "string",
                    "description": "对研究进度、发现、空白和下一步的详细反思",
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "已收集的关键发现列表（可选）",
                },
                "gaps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "还需要填补的信息空白列表（可选）",
                },
                "decision": {
                    "type": "string",
                    "enum": ["continue", "complete", "delegate"],
                    "description": "决策：continue=继续搜索，complete=完成研究，delegate=委托子智能体",
                },
            },
            "required": ["reflection"],
        }

    async def execute(self, **kwargs: Any) -> str:
        reflection = kwargs.get("reflection", "")
        findings = kwargs.get("findings", [])
        gaps = kwargs.get("gaps", [])
        decision = kwargs.get("decision", "continue")

        result = {
            "status": "reflection_recorded",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reflection": reflection,
            "decision": decision,
        }

        if findings:
            result["findings_count"] = len(findings)
            result["findings"] = findings

        if gaps:
            result["gaps_count"] = len(gaps)
            result["gaps"] = gaps

        # Provide decision guidance
        guidance_map = {
            "continue": "继续搜索以填补信息空白",
            "complete": "信息充足，可以开始整理和撰写报告",
            "delegate": "使用 spawn 工具委托子智能体进行并行研究"
        }
        result["guidance"] = guidance_map.get(decision, "")

        return json.dumps(result, ensure_ascii=False, indent=2)
