"""Tree-based conversation session (Pi-inspired).

Instead of a flat list, messages form a tree where each node has a parent_id.
This enables:
- Branching: fork from any point to explore alternatives
- History: trace any branch back to root for linear context
- Persistence: stored as JSONL with node IDs

Backward compatible — linear sessions are just trees with no forks.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


def _new_id() -> str:
    """Generate a short unique message ID."""
    return uuid.uuid4().hex[:12]


@dataclass
class MessageNode:
    """A single message in the conversation tree."""

    id: str
    parent_id: str | None
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    children: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "parent_id": self.parent_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessageNode":
        return cls(
            id=data["id"],
            parent_id=data.get("parent_id"),
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )


class TreeSession:
    """Tree-structured conversation session.

    Each message is a node with an id and parent_id.
    ``current_leaf`` tracks the active branch tip.
    ``get_history()`` walks from current_leaf back to root.

    Usage::

        tree = TreeSession(key="feishu:user123")
        tree.add_message("user", "hello")
        tree.add_message("assistant", "hi there!")

        # Fork from an earlier point
        old_node_id = tree.nodes_list[0].id
        tree.fork(old_node_id)
        tree.add_message("user", "try something else")

        # Get linear history for current branch
        history = tree.get_history()
    """

    def __init__(self, key: str):
        self.key = key
        self.nodes: dict[str, MessageNode] = {}
        self.root_ids: list[str] = []  # top-level message IDs (no parent)
        self.current_leaf: str | None = None
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()
        self.session_metadata: dict[str, Any] = {}

    # ── Core operations ──

    def add_message(
        self, role: str, content: str, **kwargs: Any
    ) -> MessageNode:
        """Add a message as a child of current_leaf."""
        node = MessageNode(
            id=_new_id(),
            parent_id=self.current_leaf,
            role=role,
            content=content,
            metadata=kwargs,
        )
        self.nodes[node.id] = node

        # Link parent → child
        if node.parent_id and node.parent_id in self.nodes:
            parent = self.nodes[node.parent_id]
            if node.id not in parent.children:
                parent.children.append(node.id)
        else:
            self.root_ids.append(node.id)

        self.current_leaf = node.id
        self.updated_at = datetime.now()
        return node

    def fork(self, from_node_id: str) -> None:
        """Move current_leaf to an existing node, enabling branching.

        Next ``add_message`` will create a new child of ``from_node_id``,
        effectively forking the conversation.
        """
        if from_node_id not in self.nodes:
            raise ValueError(f"Node {from_node_id} not found")
        self.current_leaf = from_node_id
        logger.info(f"[TreeSession] Forked to node {from_node_id}")

    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """Walk from current_leaf to root, return linear history (oldest first).

        Returns messages in LLM format: [{role, content}, ...]
        """
        if not self.current_leaf or self.current_leaf not in self.nodes:
            return []

        # Walk up the tree
        chain: list[MessageNode] = []
        node_id: str | None = self.current_leaf
        while node_id and node_id in self.nodes:
            chain.append(self.nodes[node_id])
            node_id = self.nodes[node_id].parent_id

        # Reverse to get oldest-first
        chain.reverse()

        # Trim to max_messages
        if len(chain) > max_messages:
            chain = chain[-max_messages:]

        return [{"role": n.role, "content": n.content} for n in chain]

    def get_branch_ids(self) -> list[str]:
        """Get all leaf node IDs (branches)."""
        all_parents = {n.parent_id for n in self.nodes.values() if n.parent_id}
        return [nid for nid in self.nodes if nid not in all_parents]

    def get_branch_count(self) -> int:
        """Number of distinct branches (leaf nodes)."""
        return len(self.get_branch_ids())

    def get_fork_points(self) -> list[str]:
        """Get node IDs that have multiple children (fork points)."""
        return [
            nid for nid, node in self.nodes.items()
            if len(node.children) > 1
        ]

    @property
    def nodes_list(self) -> list[MessageNode]:
        """All nodes in insertion order."""
        return list(self.nodes.values())

    @property
    def message_count(self) -> int:
        return len(self.nodes)

    # ── Backward compatibility ──

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Flat message list for backward compatibility.

        Returns ALL messages in the current branch as dicts.
        """
        if not self.current_leaf:
            return []
        chain: list[MessageNode] = []
        node_id: str | None = self.current_leaf
        while node_id and node_id in self.nodes:
            chain.append(self.nodes[node_id])
            node_id = self.nodes[node_id].parent_id
        chain.reverse()
        return [n.to_dict() for n in chain]

    def clear(self) -> None:
        """Clear all messages."""
        self.nodes.clear()
        self.root_ids.clear()
        self.current_leaf = None
        self.updated_at = datetime.now()

    # ── Serialization ──

    def to_jsonl(self) -> str:
        """Serialize to JSONL string."""
        lines = []
        # Metadata line
        meta = {
            "_type": "tree_metadata",
            "key": self.key,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_leaf": self.current_leaf,
            "metadata": self.session_metadata,
        }
        lines.append(json.dumps(meta, ensure_ascii=False))

        # Node lines (in insertion order)
        for node in self.nodes.values():
            lines.append(json.dumps(node.to_dict(), ensure_ascii=False))

        return "\n".join(lines) + "\n"

    @classmethod
    def from_jsonl(cls, key: str, text: str) -> "TreeSession":
        """Deserialize from JSONL string."""
        tree = cls(key=key)

        for line in text.strip().split("\n"):
            if not line.strip():
                continue
            data = json.loads(line)

            if data.get("_type") == "tree_metadata":
                tree.current_leaf = data.get("current_leaf")
                tree.session_metadata = data.get("metadata", {})
                if data.get("created_at"):
                    tree.created_at = datetime.fromisoformat(data["created_at"])
                if data.get("updated_at"):
                    tree.updated_at = datetime.fromisoformat(data["updated_at"])

            elif data.get("_type") == "metadata":
                # Legacy linear session metadata — convert
                tree.session_metadata = data.get("metadata", {})
                if data.get("created_at"):
                    tree.created_at = datetime.fromisoformat(data["created_at"])

            elif "id" in data and "role" in data:
                # Tree node
                node = MessageNode.from_dict(data)
                tree.nodes[node.id] = node
                if node.parent_id and node.parent_id in tree.nodes:
                    parent = tree.nodes[node.parent_id]
                    if node.id not in parent.children:
                        parent.children.append(node.id)
                else:
                    if node.id not in tree.root_ids:
                        tree.root_ids.append(node.id)

            elif "role" in data and "content" in data:
                # Legacy linear message — auto-assign IDs and chain
                node = MessageNode(
                    id=_new_id(),
                    parent_id=tree.current_leaf,
                    role=data["role"],
                    content=data["content"],
                    timestamp=data.get("timestamp", ""),
                )
                tree.nodes[node.id] = node
                if node.parent_id and node.parent_id in tree.nodes:
                    parent = tree.nodes[node.parent_id]
                    if node.id not in parent.children:
                        parent.children.append(node.id)
                else:
                    tree.root_ids.append(node.id)
                tree.current_leaf = node.id

        # If no current_leaf set, use the last node
        if not tree.current_leaf and tree.nodes:
            tree.current_leaf = list(tree.nodes.keys())[-1]

        return tree
