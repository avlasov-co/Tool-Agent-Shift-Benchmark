from __future__ import annotations
from src.core.types import AgentAction, AgentDecision
from .base import BaseAgent


class ValidateThenActAgent(BaseAgent):
    name = "validate_then_act"

    def decide(self, env, response):
        obs = response.observation
        reasons = []
        for field in getattr(env, "required_fields", []):
            if field not in obs.data:
                reasons.append(f"missing:{field}")
        if obs.schema_version != "v1":
            reasons.append("schema_drift")
        if getattr(env, "current_time", obs.timestamp) - obs.timestamp > 3:
            reasons.append("stale_observation")
        if "conflicting_views" in obs.data:
            reasons.append("conflict")
        if reasons:
            return AgentDecision(self.name, AgentAction("abstain", abstain=True, reason="validation_failed"), 0.95, reasons)
        action = env.recommended_action(obs.data)
        ok, constraint_reasons = env.validate_action(action, obs)
        if not ok:
            return AgentDecision(self.name, AgentAction("abstain", abstain=True, reason="constraint_validation_failed"), 0.95, constraint_reasons)
        return AgentDecision(self.name, action, 0.80, ["validated_then_acted"])
