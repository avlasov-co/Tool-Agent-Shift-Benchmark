from __future__ import annotations

from dataclasses import replace

from tool_agent_shift_benchmark.core.schema_registry import (
    SCHEMA_REGISTRY_CONTRACT,
    adapt_to_source_schema,
    schema_delta_from_metadata,
)
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision

from .base import BaseAgent


class ValidateThenActAgent(BaseAgent):
    name = "validate_then_act"
    version = "2.0.0"
    capabilities = (SCHEMA_REGISTRY_CONTRACT,)

    def decide(self, context, response):
        obs = response.observation
        reasons = []
        adaptation = None
        if obs.schema_version != "v1":
            delta = schema_delta_from_metadata(response.metadata)
            if delta is None:
                reasons.append("schema_drift_without_valid_registry_delta")
            else:
                adaptation = adapt_to_source_schema(obs.data, delta)
                if adaptation.succeeded:
                    obs = replace(obs, data=adaptation.data, schema_version=delta.source_schema.version)
                else:
                    reasons.extend(f"schema_incompatible:{error}" for error in adaptation.errors)
        for field in context.required_fields:
            if field not in obs.data:
                reasons.append(f"missing:{field}")
        if obs.schema_version != "v1":
            reasons.append("schema_drift")
        if context.current_time - obs.timestamp > 3:
            reasons.append("stale_observation")
        if "conflicting_views" in obs.data:
            reasons.append("conflict")
        if reasons:
            return AgentDecision(
                self.name,
                AgentAction("abstain", abstain=True, reason="validation_failed"),
                0.95,
                reasons,
                {"schema_adaptation": adaptation.to_dict() if adaptation is not None else None},
            )
        action = context.recommended_action(obs.data)
        ok, constraint_reasons = context.validate_action(action, obs)
        if not ok:
            return AgentDecision(
                self.name,
                AgentAction("abstain", abstain=True, reason="constraint_validation_failed"),
                0.95,
                constraint_reasons,
                {"schema_adaptation": adaptation.to_dict() if adaptation is not None else None},
            )
        return AgentDecision(
            self.name,
            action,
            0.80,
            ["schema_adapted_then_acted" if adaptation is not None else "validated_then_acted"],
            {"schema_adaptation": adaptation.to_dict() if adaptation is not None else None},
        )
