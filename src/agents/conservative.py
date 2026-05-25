from __future__ import annotations
from src.core.types import AgentAction, AgentDecision
from .base import BaseAgent


class ConservativeAbstentionAgent(BaseAgent):
    name = "conservative"

    def decide(self, context, response):
        obs = response.observation
        uncertainty = []
        if obs.schema_version != "v1":
            uncertainty.append("schema_not_baseline")
        if context.current_time - obs.timestamp > 0:
            uncertainty.append("not_current_timestamp")
        if "conflicting_views" in obs.data:
            uncertainty.append("conflict")
        for field in context.required_fields:
            if field not in obs.data:
                uncertainty.append(f"missing:{field}")
        candidate = context.recommended_action(obs.data)
        ok, reasons = context.validate_action(candidate, obs)
        if uncertainty or not ok:
            return AgentDecision(self.name, AgentAction("abstain", abstain=True, reason="conservative_uncertainty"), 0.98, uncertainty + reasons)
        return AgentDecision(self.name, candidate, 0.65, ["low_uncertainty"])
