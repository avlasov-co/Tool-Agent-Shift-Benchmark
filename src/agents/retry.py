from __future__ import annotations
from src.core.types import AgentAction, AgentDecision
from .base import BaseAgent


class RetryAgent(BaseAgent):
    name = "retry"

    def decide(self, env, response):
        data = response.observation.data
        missing = [f for f in getattr(env, "required_fields", []) if f not in data]
        if missing:
            clean = env.tool_response()
            action = env.recommended_action(clean.observation.data)
            return AgentDecision(self.name, action, 0.70, ["retried_after_invalid_output"], {"retry": True, "missing": missing})
        action = env.recommended_action(data)
        return AgentDecision(self.name, action, 0.75, ["no_retry_needed"], {"retry": False})
