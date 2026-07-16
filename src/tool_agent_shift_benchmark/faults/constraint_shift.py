from __future__ import annotations

import math
from random import Random
from typing import Any

from tool_agent_shift_benchmark.core.serialization import canonicalize, stable_hash

from .base import BaseFault, clone_response


class ConstraintShiftFault(BaseFault):
    name = "constraint_shift"
    channel = "constraint_visibility"
    mechanism = "temporal_policy_constraint_divergence"
    severity_semantics = "number and magnitude of visible constraints diverging from the execution-time reference"
    schedule_behavior = "changes the visible constraint revision only on active scheduled lifecycle steps"
    detection_path = "track visible constraint revisions and revalidate against fresh policy-visible constraints"
    adaptation_path = "adopt the new visible revision, reobserve before execution, or abstain"

    @staticmethod
    def _candidate_changes(environment: str, constraints: dict[str, Any], severity: float) -> list[tuple[str, Any]]:
        if environment == "file_ops":
            age = int(constraints.get("archive_age_days", 60))
            return [
                ("archive_age_days", max(0, age - max(1, math.ceil(age * 0.5 * severity)))),
                ("protect_hidden", False),
                ("allowed_root", "/"),
            ]
        if environment == "calendar_ops":
            end = int(constraints.get("working_hours_end", 17))
            return [
                ("working_hours_end", end + max(1, math.ceil(3 * severity))),
                ("timezone", "UTC+00:00"),
                ("working_hours_start", max(0, int(constraints.get("working_hours_start", 9)) - 2)),
            ]
        if environment == "risk_ops":
            limit = int(constraints.get("risk_limit", 60))
            volatility = float(constraints.get("max_volatility_for_increase", 0.2))
            adjustment = int(constraints.get("max_adjustment", 10))
            return [
                ("risk_limit", limit + max(1, math.ceil(20 * severity))),
                ("max_volatility_for_increase", round(volatility + 0.2 * severity, 6)),
                ("max_adjustment", adjustment + max(1, math.ceil(10 * severity))),
            ]
        return []

    def apply(self, response, env, rng: Random):
        constraints = canonicalize(response.observation.constraints)
        if not isinstance(constraints, dict):
            raise TypeError("observation constraints must be a mapping")
        environment = response.observation.env_name
        candidates = self._candidate_changes(environment, constraints, self.severity)
        change_count = 0 if self.severity == 0.0 else min(len(candidates), math.ceil(self.severity * len(candidates)))
        # Constraint priority is semantic; RNG consumption binds the operation
        # to the local fault stream without randomly changing monotonicity.
        rng.randrange(2**31)
        before = dict(constraints)
        deltas: dict[str, dict[str, Any]] = {}
        for key, value in candidates[:change_count]:
            previous = constraints.get(key)
            if previous != value:
                constraints[key] = value
                deltas[key] = {"before": previous, "after": value}
        hidden_constraints = getattr(env, "visible_constraints", lambda: {})()
        hidden_reference_hash = stable_hash(hidden_constraints, prefix="constraint_reference")
        effective_at = int(getattr(env, "current_time", response.observation.timestamp))
        phase = str(getattr(env, "lifecycle_phase", "unknown"))
        visible_revision = stable_hash(
            {
                "environment": environment,
                "effective_at": effective_at,
                "phase": phase,
                "constraints": constraints,
            },
            prefix="constraint_revision",
        )
        effect = self._effect(
            "temporal_constraint_divergence",
            len(deltas) / len(candidates) if candidates else 0.0,
            {
                "visible_constraints_before": before,
                "visible_constraints_after": constraints,
                "hidden_constraint_reference_hash": hidden_reference_hash,
                "constraint_deltas": deltas,
                "changed_constraint_count": len(deltas),
                "candidate_constraint_count": len(candidates),
                "effective_at": effective_at,
                "lifecycle_phase": phase,
                "visible_constraint_revision": visible_revision,
            },
        )
        metadata = self._record(response, effect)
        if deltas:
            metadata["constraint_context"] = {
                "visibility": "policy_visible",
                "effective_at": effective_at,
                "lifecycle_phase": phase,
                "changed_keys": sorted(deltas),
                "visible_constraint_revision": visible_revision,
            }
        return clone_response(response, constraints=constraints, metadata=metadata)
