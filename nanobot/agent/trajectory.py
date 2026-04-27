"""Conversation trajectory saving for analysis and training.

Ported from Hermes Agent (agent/trajectory.py) with adaptations:
- Uses loguru instead of stdlib logging
- Saves to workspace/trajectories/ directory
- Adds session metadata (channel, chat_id, duration)

Each conversation is saved as a JSONL entry in ShareGPT format,
enabling future RL training, quality analysis, and debugging.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


def save_trajectory(
    messages: list[dict[str, Any]],
    model: str,
    completed: bool = True,
    workspace: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path | None:
    """Save a conversation trajectory to a JSONL file.

    Args:
        messages: The conversation messages (system + user + assistant + tool).
        model: Model name used for this conversation.
        completed: Whether the conversation completed successfully.
        workspace: Workspace directory. Defaults to ~/.nanobot/workspace.
        metadata: Optional extra metadata (channel, chat_id, duration, etc.).

    Returns:
        Path to the trajectory file, or None on failure.
    """
    if not messages:
        return None

    # Determine output directory
    if workspace is None:
        workspace = Path.home() / ".nanobot" / "workspace"
    traj_dir = workspace / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)

    # Choose filename based on success/failure
    today = datetime.now().strftime("%Y-%m-%d")
    if completed:
        filename = traj_dir / f"trajectories_{today}.jsonl"
    else:
        filename = traj_dir / f"failed_{today}.jsonl"

    # Convert messages to lightweight ShareGPT format
    conversations = _to_sharegpt(messages)

    entry = {
        "conversations": conversations,
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "completed": completed,
        "num_turns": len([m for m in messages if m.get("role") == "user"]),
        "num_tool_calls": len([m for m in messages if m.get("role") == "tool"]),
    }

    if metadata:
        entry["metadata"] = metadata

    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.debug(f"[Trajectory] Saved to {filename}")
        return filename
    except Exception as e:
        logger.warning(f"[Trajectory] Failed to save: {e}")
        return None


def _to_sharegpt(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert internal message format to ShareGPT format.

    ShareGPT format: [{"from": "system/human/gpt/tool", "value": "..."}]

    Args:
        messages: Internal message list.

    Returns:
        ShareGPT-formatted conversation list.
    """
    role_map = {
        "system": "system",
        "user": "human",
        "assistant": "gpt",
        "tool": "tool",
    }

    result = []
    for msg in messages:
        role = msg.get("role", "user")
        sharegpt_role = role_map.get(role, role)

        # Build value
        content = msg.get("content", "")
        if isinstance(content, list):
            # Multimodal content — extract text parts only
            text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            content = "\n".join(text_parts) if text_parts else "[multimodal content]"

        # Add reasoning if present (wrap in <think> tags)
        reasoning = msg.get("reasoning_content", "")
        if reasoning:
            content = f"<think>\n{reasoning}\n</think>\n{content}"

        # Add tool call info for assistant messages
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            tc_strs = []
            for tc in tool_calls:
                func = tc.get("function", {})
                tc_strs.append(f"[tool_call: {func.get('name', '?')}({func.get('arguments', '')})]")
            if content:
                content = content + "\n" + "\n".join(tc_strs)
            else:
                content = "\n".join(tc_strs)

        # Add tool name for tool results
        tool_name = msg.get("name", "")
        if role == "tool" and tool_name:
            content = f"[{tool_name}] {content}"

        result.append({
            "from": sharegpt_role,
            "value": content or "",
        })

    return result


def get_trajectory_stats(workspace: Path | None = None) -> dict[str, Any]:
    """Get statistics about saved trajectories.

    Args:
        workspace: Workspace directory.

    Returns:
        Dict with trajectory counts and sizes.
    """
    if workspace is None:
        workspace = Path.home() / ".nanobot" / "workspace"
    traj_dir = workspace / "trajectories"

    if not traj_dir.exists():
        return {"total_files": 0, "total_entries": 0, "total_size_kb": 0}

    total_entries = 0
    total_size = 0
    files = list(traj_dir.glob("*.jsonl"))

    for f in files:
        total_size += f.stat().st_size
        with open(f, encoding="utf-8") as fh:
            total_entries += sum(1 for _ in fh)

    return {
        "total_files": len(files),
        "total_entries": total_entries,
        "total_size_kb": round(total_size / 1024, 1),
    }
