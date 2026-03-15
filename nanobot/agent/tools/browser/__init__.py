"""Browser automation tools module using Playwright."""

from nanobot.agent.tools.browser.browser_tools import (
    BrowserClickTool,
    BrowserDownloadTool,
    BrowserExecuteJSTool,
    BrowserExtractTool,
    BrowserFillFormTool,
    BrowserLoadSessionTool,
    BrowserLoginTool,
    BrowserOpenTool,
    BrowserScreenshotTool,
    BrowserWaitTool,
)

BROWSER_TOOLS = [
    BrowserOpenTool,
    BrowserScreenshotTool,
    BrowserClickTool,
    BrowserFillFormTool,
    BrowserLoginTool,
    BrowserLoadSessionTool,
    BrowserExtractTool,
    BrowserDownloadTool,
    BrowserExecuteJSTool,
    BrowserWaitTool,
]

__all__ = [
    "BROWSER_TOOLS",
    "BrowserOpenTool",
    "BrowserScreenshotTool",
    "BrowserClickTool",
    "BrowserFillFormTool",
    "BrowserLoginTool",
    "BrowserLoadSessionTool",
    "BrowserExtractTool",
    "BrowserDownloadTool",
    "BrowserExecuteJSTool",
    "BrowserWaitTool",
]
