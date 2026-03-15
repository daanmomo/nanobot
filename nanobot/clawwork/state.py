"""ClawWork shared state object."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClawWorkState:
    """Mutable state shared across all ClawWork tools within a session."""

    economic_tracker: Any  # EconomicTracker
    task_manager: Any | None = None  # TaskManager (optional)
    evaluator: Any | None = None  # WorkEvaluator (optional)
    signature: str = ""
    current_date: str | None = None
    current_task: dict | None = None
    data_path: str = ""
    supports_multimodal: bool = True
    enable_file_reading: bool = True
