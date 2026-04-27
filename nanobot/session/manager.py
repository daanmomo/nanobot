"""Session management for conversation history.

v2 — Tree-based sessions (Pi-inspired):
  - Messages stored as tree nodes with id/parent_id
  - Supports branching (fork from any point)
  - Backward compatible with legacy linear JSONL files
  - SessionManager auto-migrates old sessions on load
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from nanobot.session.tree import TreeSession
from nanobot.utils.helpers import ensure_dir, safe_filename


class SessionManager:
    """
    Manages conversation sessions with tree-based storage.

    Sessions are stored as JSONL files in the sessions directory.
    Each message is a tree node with id and parent_id, enabling branching.
    Legacy linear sessions are auto-migrated on load.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(Path.home() / ".nanobot" / "sessions")
        self._cache: dict[str, TreeSession] = {}

    def _get_session_path(self, key: str) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def get_or_create(self, key: str) -> TreeSession:
        """
        Get an existing session or create a new one.

        Args:
            key: Session key (usually channel:chat_id).

        Returns:
            The tree session.
        """
        # Check cache
        if key in self._cache:
            return self._cache[key]

        # Try to load from disk
        session = self._load(key)
        if session is None:
            session = TreeSession(key=key)

        self._cache[key] = session
        return session

    def _load(self, key: str) -> TreeSession | None:
        """Load a session from disk. Auto-migrates legacy linear format."""
        path = self._get_session_path(key)

        if not path.exists():
            return None

        try:
            text = path.read_text(encoding="utf-8")
            if not text.strip():
                return None

            tree = TreeSession.from_jsonl(key, text)
            logger.debug(
                f"[Session] Loaded {key}: {tree.message_count} messages, "
                f"{tree.get_branch_count()} branches"
            )
            return tree

        except Exception as e:
            logger.warning(f"Failed to load session {key}: {e}")
            return None

    def save(self, session: TreeSession) -> None:
        """Save a session to disk."""
        path = self._get_session_path(session.key)

        try:
            path.write_text(session.to_jsonl(), encoding="utf-8")
            self._cache[session.key] = session
        except Exception as e:
            logger.error(f"Failed to save session {session.key}: {e}")

    def delete(self, key: str) -> bool:
        """
        Delete a session.

        Args:
            key: Session key.

        Returns:
            True if deleted, False if not found.
        """
        # Remove from cache
        self._cache.pop(key, None)

        # Remove file
        path = self._get_session_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def fork_session(self, key: str, from_node_id: str) -> TreeSession:
        """Fork a session from a specific message node.

        Args:
            key: Session key.
            from_node_id: Node ID to fork from.

        Returns:
            The session with current_leaf set to from_node_id.
        """
        session = self.get_or_create(key)
        session.fork(from_node_id)
        self.save(session)
        return session

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions with metadata.

        Returns:
            List of session info dicts.
        """
        sessions = []

        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        _type = data.get("_type", "")
                        if _type in ("metadata", "tree_metadata"):
                            sessions.append({
                                "key": path.stem.replace("_", ":"),
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                                "tree": _type == "tree_metadata",
                                "path": str(path),
                            })
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

    def get_session_info(self, key: str) -> dict[str, Any] | None:
        """Get detailed info about a session.

        Returns:
            Dict with message count, branch count, fork points, etc.
        """
        session = self.get_or_create(key)
        if not session.nodes:
            return None

        return {
            "key": key,
            "message_count": session.message_count,
            "branch_count": session.get_branch_count(),
            "fork_points": len(session.get_fork_points()),
            "current_leaf": session.current_leaf,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }
