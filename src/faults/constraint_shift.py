from __future__ import annotations
from random import Random
from .base import BaseFault, clone_response


class ConstraintShiftFault(BaseFault):
    name = "constraint_shift"

    def apply(self, response, env, rng: Random):
        constraints = dict(response.observation.constraints)
        if response.observation.env_name == "file_ops":
            constraints["protect_hidden"] = False
        elif response.observation.env_name == "calendar_ops":
            constraints["working_hours_end"] = 19
            constraints["timezone"] = "UTC+00:00"
        elif response.observation.env_name == "risk_ops":
            constraints["risk_limit"] = constraints.get("risk_limit", 60) + 20
        meta = dict(response.observation.metadata)
        meta.setdefault("faults", []).append({"name": self.name, "metadata": {"visible_constraints_shifted": True}})
        return clone_response(response, constraints=constraints, metadata=meta)
