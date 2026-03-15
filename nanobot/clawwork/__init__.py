"""
ClawWork - Economic tracking system for AI agents.

Transforms AI assistants into "AI coworkers" that:
- Track token costs (every LLM call costs money from a balance)
- Earn income by completing tasks evaluated by quality
- Maintain economic solvency

Enable via config.json:
{
  "agents": {
    "clawwork": {
      "enabled": true,
      "signature": "my-agent",
      "initialBalance": 1000.0,
      "tokenPricing": {"inputPrice": 2.5, "outputPrice": 10.0}
    }
  }
}
"""

from nanobot.clawwork.state import ClawWorkState
from nanobot.clawwork.economic_tracker import EconomicTracker
from nanobot.clawwork.agent_loop import ClawWorkAgentLoop
from nanobot.clawwork.tools import (
    DecideActivityTool,
    SubmitWorkTool,
    LearnTool,
    GetStatusTool,
)
from nanobot.clawwork.artifact_tools import CreateArtifactTool, ReadArtifactTool
from nanobot.clawwork.provider_wrapper import TrackedProvider, CostCapturingLiteLLMProvider
from nanobot.clawwork.task_classifier import TaskClassifier

__all__ = [
    "ClawWorkState",
    "EconomicTracker",
    "ClawWorkAgentLoop",
    "DecideActivityTool",
    "SubmitWorkTool",
    "LearnTool",
    "GetStatusTool",
    "CreateArtifactTool",
    "ReadArtifactTool",
    "TrackedProvider",
    "CostCapturingLiteLLMProvider",
    "TaskClassifier",
]
