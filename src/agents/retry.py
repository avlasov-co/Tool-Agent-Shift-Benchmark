from __future__ import annotations
from src.core.types import AgentAction, AgentDecision
from .base import BaseAgent


class RetryAgent(BaseAgent):
    name = "retry"

    def decide(self, context, response):
        data = response.observation.data
        missing = [field for field in context.required_fields if field not in data]
        if missing:
            return AgentDecision(
                self.name,
                AgentAction("abstain", abstain=True, reason="retry_unavailable_after_faulted_observation"),
                0.80,
                ["missing_required_visible_fields"],
                {"retry": False, "missing": missing, "clean_tool_bypass_prevented": True},
            )
        action = context.recommended_action(data)
        return AgentDecision(self.name, action, 0.75, ["no_retry_needed"], {"retry": False})
