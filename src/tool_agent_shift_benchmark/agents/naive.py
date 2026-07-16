from __future__ import annotations

from tool_agent_shift_benchmark.core.types import AgentDecision

from .base import BaseAgent


class NaiveAgent(BaseAgent):
    name = "naive"

    def decide(self, context, response):
        action = context.recommended_action(response.observation.data)
        return AgentDecision(self.name, action, 0.85, ["acted_on_tool_output_directly"])
