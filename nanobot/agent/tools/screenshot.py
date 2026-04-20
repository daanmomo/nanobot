"""Screenshot tool — capture screen and return as visual input for the agent."""

import asyncio
import base64
import tempfile
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool

# Max width to keep image size reasonable for LLM input
MAX_WIDTH = 1280


class ScreenshotTool(Tool):
    """Capture a screenshot of the entire screen or a specific window."""

    @property
    def name(self) -> str:
        return "screenshot"

    @property
    def description(self) -> str:
        return (
            "Capture a screenshot of the screen and return it as an image you can see. "
            "Essential for Computer Use — lets you visually inspect what's on screen. "
            "Returns the image directly in your visual input. "
            "You can capture the full screen, a specific region, or a specific window by title."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": (
                        "Capture region as 'x,y,width,height' (e.g. '0,0,800,600'). "
                        "Omit for full screen."
                    ),
                },
                "window_title": {
                    "type": "string",
                    "description": (
                        "Capture a specific window by title (e.g. '企业微信', 'Safari'). "
                        "Uses partial match on window title or app name."
                    ),
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> "str | list[dict[str, Any]]":
        region = kwargs.get("region")
        window_title = kwargs.get("window_title")

        # Capture as PNG first (lossless), then convert to JPEG for size
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            png_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            jpg_path = f.name

        try:
            # Build screencapture command
            cmd = ["screencapture", "-x"]  # -x = no sound

            if window_title:
                window_id = await self._find_window_id(window_title)
                if window_id:
                    cmd.extend(["-l", str(window_id)])
                else:
                    return f"Error: No window found matching '{window_title}'"
            elif region:
                parts = region.split(",")
                if len(parts) == 4:
                    x, y, w, h = [p.strip() for p in parts]
                    cmd.extend(["-R", f"{x},{y},{w},{h}"])
                else:
                    return "Error: region must be 'x,y,width,height'"

            cmd.append(png_path)

            # Execute screencapture
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

            if proc.returncode != 0:
                return f"Error: screencapture failed: {stderr.decode()}"

            path = Path(png_path)
            if not path.exists() or path.stat().st_size == 0:
                return "Error: Screenshot file is empty"

            # Resize to max width and convert to JPEG using sips
            await self._optimize_image(png_path, jpg_path)

            # Read optimized image
            final_path = Path(jpg_path)
            if not final_path.exists() or final_path.stat().st_size == 0:
                # Fallback to PNG if JPEG conversion failed
                final_path = path
                mime = "image/png"
            else:
                mime = "image/jpeg"

            image_data = final_path.read_bytes()
            b64_data = base64.b64encode(image_data).decode()
            size_kb = len(image_data) / 1024

            # Build description
            desc_parts = ["Screenshot captured"]
            if window_title:
                desc_parts.append(f"(window: {window_title})")
            elif region:
                desc_parts.append(f"(region: {region})")
            else:
                desc_parts.append("(full screen)")
            desc_parts.append(f"[{size_kb:.0f}KB]")
            description = " ".join(desc_parts)

            # Return multimodal content — the image goes directly into visual input
            return [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64_data}"},
                },
                {
                    "type": "text",
                    "text": description,
                },
            ]

        finally:
            Path(png_path).unlink(missing_ok=True)
            Path(jpg_path).unlink(missing_ok=True)

    async def _find_window_id(self, title: str) -> int | None:
        """Find a window ID by partial title match."""
        python_script = f"""
import Quartz
windows = Quartz.CGWindowListCopyWindowInfo(
    Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
    Quartz.kCGNullWindowID
)
for w in windows:
    name = w.get('kCGWindowName', '') or ''
    owner = w.get('kCGWindowOwnerName', '') or ''
    layer = w.get('kCGWindowLayer', 0)
    # Skip menu bar items and system UI
    if layer != 0:
        continue
    if '{title}' in name or '{title}' in owner:
        wid = w.get('kCGWindowNumber', 0)
        if wid:
            print(wid)
            break
"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", "-c", python_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            wid = stdout.decode().strip()
            return int(wid) if wid else None
        except Exception:
            return None

    async def _optimize_image(self, png_path: str, jpg_path: str) -> None:
        """Resize to max width and convert to JPEG for smaller size."""
        try:
            # Get current width
            proc = await asyncio.create_subprocess_exec(
                "sips", "-g", "pixelWidth", png_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            width_line = [l for l in stdout.decode().split("\n") if "pixelWidth" in l]

            current_width = MAX_WIDTH + 1  # default: needs resize
            if width_line:
                current_width = int(width_line[0].split(":")[-1].strip())

            # Resize if wider than MAX_WIDTH
            if current_width > MAX_WIDTH:
                await (await asyncio.create_subprocess_exec(
                    "sips", "--resampleWidth", str(MAX_WIDTH), png_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )).communicate()

            # Convert to JPEG with quality 60
            await (await asyncio.create_subprocess_exec(
                "sips", "-s", "format", "jpeg",
                "-s", "formatOptions", "60",
                png_path, "--out", jpg_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )).communicate()

        except Exception:
            pass  # If optimization fails, caller will fallback to PNG


SCREENSHOT_TOOLS = [ScreenshotTool]
