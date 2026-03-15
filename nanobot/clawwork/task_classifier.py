"""
TaskClassifier - classifies free-form instructions into an occupation
category with an estimated task value (hours x hourly_wage).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger


# Default fallback occupation
_FALLBACK_OCCUPATION = "General and Operations Managers"
_FALLBACK_WAGE = 64.0

_CLASSIFICATION_PROMPT = """\
You are a task classifier. Given a task instruction, you must:
1. Pick the single best-fit occupation from the list below.
2. Estimate how many hours a professional in that occupation would need (0.25-40).
3. Return ONLY valid JSON, no markdown fences.

Occupations (with hourly wages):
{occupation_list}

Task instruction:
{instruction}

Respond with ONLY this JSON structure:
{{"occupation": "<exact occupation name from list>", "hours_estimate": <number>, "reasoning": "<one sentence>"}}"""


class TaskClassifier:
    """Classifies task instructions into occupations and estimates value."""

    def __init__(self, provider: Any, wage_mapping_path: str | Path | None = None) -> None:
        """
        Args:
            provider: A nanobot LLMProvider (or TrackedProvider wrapper)
            wage_mapping_path: Path to occupation-to-wage mapping JSON
        """
        self._provider = provider
        self._occupations: dict[str, float] = {}  # name -> hourly_wage
        self._wage_mapping_path = Path(wage_mapping_path) if wage_mapping_path else None
        self._load_occupations()

    def _load_occupations(self) -> None:
        """Load the occupation-to-wage mapping JSON."""
        if not self._wage_mapping_path or not self._wage_mapping_path.exists():
            logger.warning("Wage mapping not found, using fallback only")
            # Add some common occupations as fallback
            self._occupations = {
                "Software Developers": 60.0,
                "Financial Analysts": 45.0,
                "Marketing Specialists": 35.0,
                "Administrative Assistants": 22.0,
                "General and Operations Managers": 64.0,
                "Data Scientists": 55.0,
                "Writers and Authors": 35.0,
                "Accountants": 40.0,
                "Project Managers": 50.0,
                "Customer Service Representatives": 20.0,
            }
            return

        try:
            data = json.loads(self._wage_mapping_path.read_text())
            for entry in data:
                name = entry.get("gdpval_occupation", "") or entry.get("occupation", "")
                wage = entry.get("hourly_wage")
                if name and wage:
                    self._occupations[name] = float(wage)
            logger.info(f"Loaded {len(self._occupations)} occupations for classification")
        except Exception as exc:
            logger.error(f"Failed to load occupation mapping: {exc}")

    def _fuzzy_match(self, name: str) -> tuple[str, float]:
        """Try to match an occupation name, falling back to default."""
        if not self._occupations:
            return _FALLBACK_OCCUPATION, _FALLBACK_WAGE

        # Exact match
        if name in self._occupations:
            return name, self._occupations[name]

        # Case-insensitive match
        lower = name.lower()
        for occ, wage in self._occupations.items():
            if occ.lower() == lower:
                return occ, wage

        # Substring match
        for occ, wage in self._occupations.items():
            if lower in occ.lower() or occ.lower() in lower:
                return occ, wage

        return _FALLBACK_OCCUPATION, self._occupations.get(_FALLBACK_OCCUPATION, _FALLBACK_WAGE)

    async def classify(self, instruction: str) -> dict[str, Any]:
        """
        Classify an instruction into an occupation with estimated value.

        Returns:
            {
                "occupation": str,
                "hourly_wage": float,
                "hours_estimate": float,
                "task_value": float,
                "reasoning": str,
            }
        """
        if not self._occupations:
            return self._fallback_result(instruction)

        occupation_list = "\n".join(
            f"- {name} (${wage:.2f}/hr)" for name, wage in sorted(self._occupations.items())
        )

        prompt = _CLASSIFICATION_PROMPT.format(
            occupation_list=occupation_list,
            instruction=instruction,
        )

        try:
            response = await self._provider.chat(
                messages=[{"role": "user", "content": prompt}],
                tools=None,
                temperature=0.3,
                max_tokens=256,
            )

            text = response.content.strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            parsed = json.loads(text)

            raw_occupation = parsed.get("occupation", "")
            hours = float(parsed.get("hours_estimate", 1.0))
            hours = max(0.25, min(40.0, hours))
            reasoning = parsed.get("reasoning", "")

            occupation, wage = self._fuzzy_match(raw_occupation)
            task_value = round(hours * wage, 2)

            logger.info(f"Classified: {occupation} | {hours}h x ${wage:.2f}/hr = ${task_value:.2f}")

            return {
                "occupation": occupation,
                "hourly_wage": wage,
                "hours_estimate": hours,
                "task_value": task_value,
                "reasoning": reasoning,
            }

        except Exception as exc:
            logger.warning(f"Classification failed ({exc}), using fallback")
            return self._fallback_result(instruction)

    def _fallback_result(self, instruction: str) -> dict[str, Any]:
        """Return a safe default classification."""
        wage = self._occupations.get(_FALLBACK_OCCUPATION, _FALLBACK_WAGE)
        hours = 1.0
        return {
            "occupation": _FALLBACK_OCCUPATION,
            "hourly_wage": wage,
            "hours_estimate": hours,
            "task_value": round(hours * wage, 2),
            "reasoning": "Fallback classification",
        }
