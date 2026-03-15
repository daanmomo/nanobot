"""
Economic Tracker - Manages economic balance and token costs for ClawWork agents.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


class EconomicTracker:
    """
    Tracks economic state for a ClawWork agent including:
    - Balance (cash)
    - Token costs separated by channel (LLM, search API, OCR API, etc.)
    - Work income with evaluation score threshold
    - Survival status
    """

    def __init__(
        self,
        signature: str,
        initial_balance: float = 1000.0,
        input_token_price: float = 2.5,  # per 1M tokens
        output_token_price: float = 10.0,  # per 1M tokens
        data_path: str | None = None,
        min_evaluation_threshold: float = 0.6,
    ):
        """
        Initialize Economic Tracker.

        Args:
            signature: Agent signature/name
            initial_balance: Starting balance in dollars
            input_token_price: Price per 1M input tokens
            output_token_price: Price per 1M output tokens
            data_path: Path to store economic data
            min_evaluation_threshold: Minimum evaluation score to receive payment
        """
        self.signature = signature
        self.initial_balance = initial_balance
        self.input_token_price = input_token_price
        self.output_token_price = output_token_price
        self.min_evaluation_threshold = min_evaluation_threshold

        # Set data paths
        self.data_path = data_path or f"./data/clawwork/{signature}/economic"
        self.balance_file = os.path.join(self.data_path, "balance.jsonl")
        self.token_costs_file = os.path.join(self.data_path, "token_costs.jsonl")

        # Task-level tracking
        self.current_task_id: str | None = None
        self.current_task_date: str | None = None
        self.task_costs: dict[str, float] = {}
        self.task_start_time: str | None = None
        self.task_token_details: dict[str, Any] = {}

        # Session tracking
        self.session_input_tokens = 0
        self.session_output_tokens = 0
        self.session_cost = 0.0
        self.daily_cost = 0.0

        # Current state
        self.current_balance = initial_balance
        self.total_token_cost = 0.0
        self.total_work_income = 0.0

        # Ensure directory exists
        os.makedirs(self.data_path, exist_ok=True)

    def initialize(self) -> None:
        """Initialize tracker, load existing state or create new."""
        if os.path.exists(self.balance_file):
            self._load_latest_state()
        else:
            self._save_balance_record(
                date="initialization",
                balance=self.initial_balance,
                token_cost_delta=0.0,
                work_income_delta=0.0,
            )

    def _load_latest_state(self) -> None:
        """Load latest economic state from balance file."""
        record = None
        with open(self.balance_file, "r") as f:
            for line in f:
                record = json.loads(line)

        if record:
            self.current_balance = record["balance"]
            self.total_token_cost = record.get("total_token_cost", 0.0)
            self.total_work_income = record.get("total_work_income", 0.0)

    def start_task(self, task_id: str, date: str | None = None) -> None:
        """Start tracking costs for a new task."""
        self.current_task_id = task_id
        self.current_task_date = date or datetime.now().strftime("%Y-%m-%d")
        self.task_start_time = datetime.now().isoformat()
        self.task_costs = {
            "llm_tokens": 0.0,
            "search_api": 0.0,
            "ocr_api": 0.0,
            "other_api": 0.0,
        }
        self.task_token_details = {"llm_calls": [], "api_calls": []}

    def end_task(self) -> None:
        """End tracking for current task and save consolidated record."""
        if self.current_task_id:
            self._save_task_record()
            self.current_task_id = None
            self.current_task_date = None
            self.task_start_time = None
            self.task_costs = {}
            self.task_token_details = {}

    def track_tokens(
        self,
        input_tokens: int,
        output_tokens: int,
        api_name: str = "agent",
        cost: float | None = None,
    ) -> float:
        """
        Track token usage and calculate cost.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            api_name: Origin of the call
            cost: Pre-computed cost in dollars (e.g. from OpenRouter)

        Returns:
            Cost in dollars for this call
        """
        if cost is None:
            cost = (input_tokens / 1_000_000.0) * self.input_token_price + (
                output_tokens / 1_000_000.0
            ) * self.output_token_price

        # Update session tracking
        self.session_input_tokens += input_tokens
        self.session_output_tokens += output_tokens
        self.session_cost += cost
        self.daily_cost += cost

        # Update task-level tracking
        if self.current_task_id:
            self.task_costs["llm_tokens"] += cost
            self.task_token_details["llm_calls"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "api_name": api_name,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": cost,
                }
            )

        # Update totals
        self.total_token_cost += cost
        self.current_balance -= cost

        return cost

    def track_api_call(
        self, tokens: int, price_per_1m: float, api_name: str = "API"
    ) -> float:
        """Track API call cost based on token usage."""
        cost = (tokens / 1_000_000.0) * price_per_1m

        self.session_cost += cost
        self.daily_cost += cost

        if self.current_task_id:
            if "search" in api_name.lower() or "tavily" in api_name.lower():
                self.task_costs["search_api"] += cost
            elif "ocr" in api_name.lower():
                self.task_costs["ocr_api"] += cost
            else:
                self.task_costs["other_api"] += cost

            self.task_token_details["api_calls"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "api_name": api_name,
                    "pricing_model": "per_token",
                    "tokens": tokens,
                    "cost": cost,
                }
            )

        self.total_token_cost += cost
        self.current_balance -= cost

        return cost

    def _save_task_record(self) -> None:
        """Save consolidated task-level cost record."""
        if not self.current_task_id:
            return

        total_input = sum(
            c["input_tokens"] for c in self.task_token_details.get("llm_calls", [])
        )
        total_output = sum(
            c["output_tokens"] for c in self.task_token_details.get("llm_calls", [])
        )
        total_cost = sum(self.task_costs.values())

        task_record = {
            "timestamp_end": datetime.now().isoformat(),
            "timestamp_start": self.task_start_time,
            "date": self.current_task_date or datetime.now().strftime("%Y-%m-%d"),
            "task_id": self.current_task_id,
            "llm_usage": {
                "total_calls": len(self.task_token_details.get("llm_calls", [])),
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_cost": self.task_costs.get("llm_tokens", 0.0),
            },
            "cost_summary": {
                "llm_tokens": self.task_costs.get("llm_tokens", 0.0),
                "search_api": self.task_costs.get("search_api", 0.0),
                "ocr_api": self.task_costs.get("ocr_api", 0.0),
                "other_api": self.task_costs.get("other_api", 0.0),
                "total_cost": total_cost,
            },
            "balance_after": self.current_balance,
            "session_cost": self.session_cost,
        }

        with open(self.token_costs_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(task_record) + "\n")

    def add_work_income(
        self,
        amount: float,
        task_id: str,
        evaluation_score: float,
        description: str = "",
    ) -> float:
        """
        Add income from completed work with evaluation score threshold.

        Payment is only awarded if evaluation_score >= min_evaluation_threshold.
        """
        if evaluation_score < self.min_evaluation_threshold:
            actual_payment = 0.0
        else:
            actual_payment = amount
            self.current_balance += actual_payment
            self.total_work_income += actual_payment

        self._log_work_income(task_id, amount, actual_payment, evaluation_score, description)
        return actual_payment

    def _log_work_income(
        self,
        task_id: str,
        base_amount: float,
        actual_payment: float,
        evaluation_score: float,
        description: str,
    ) -> None:
        """Log work income to token costs file."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "date": self.current_task_date or datetime.now().strftime("%Y-%m-%d"),
            "task_id": task_id,
            "type": "work_income",
            "base_amount": base_amount,
            "actual_payment": actual_payment,
            "evaluation_score": evaluation_score,
            "threshold": self.min_evaluation_threshold,
            "payment_awarded": actual_payment > 0,
            "description": description,
            "balance_after": self.current_balance,
        }

        with open(self.token_costs_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    def _save_balance_record(
        self,
        date: str,
        balance: float,
        token_cost_delta: float,
        work_income_delta: float,
    ) -> None:
        """Save balance record to file."""
        record = {
            "date": date,
            "balance": balance,
            "token_cost_delta": token_cost_delta,
            "work_income_delta": work_income_delta,
            "total_token_cost": self.total_token_cost,
            "total_work_income": self.total_work_income,
            "survival_status": self.get_survival_status(),
        }

        with open(self.balance_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def get_balance(self) -> float:
        """Get current balance."""
        return self.current_balance

    def get_net_worth(self) -> float:
        """Get net worth (balance)."""
        return self.current_balance

    def get_survival_status(self) -> str:
        """Get survival status based on balance."""
        if self.current_balance <= 0:
            return "bankrupt"
        elif self.current_balance < 100:
            return "struggling"
        elif self.current_balance < 500:
            return "stable"
        else:
            return "thriving"

    def is_bankrupt(self) -> bool:
        """Check if agent is bankrupt."""
        return self.current_balance <= 0

    def get_session_cost(self) -> float:
        """Get current session token cost."""
        return self.session_cost

    def get_daily_cost(self) -> float:
        """Get total daily token cost."""
        return self.daily_cost

    def reset_session(self) -> None:
        """Reset session tracking."""
        self.session_input_tokens = 0
        self.session_output_tokens = 0
        self.session_cost = 0.0

    def __str__(self) -> str:
        return (
            f"EconomicTracker(signature='{self.signature}', "
            f"balance=${self.current_balance:.2f}, "
            f"status={self.get_survival_status()})"
        )
