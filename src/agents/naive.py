from __future__ import annotations
from src.core.types import AgentDecision
from .base import BaseAgent


class NaiveAgent(BaseAgent):
    name = "naive"

    def decide(self, env, response):
        action = env.recommended_action(response.observation.data)
        return AgentDecision(self.name, action, 0.85, ["acted_on_tool_output_directly"])
