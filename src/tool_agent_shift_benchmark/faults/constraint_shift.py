from __future__ import annotations

import math
from random import Random

from .base import BaseFault, clone_response


class ConstraintShiftFault(BaseFault):
    name = "constraint_shift"

    def apply(self, response, env, rng: Random):
        constraints = dict(response.observation.constraints)
        deltas = {}
        if response.observation.env_name == "file_ops":
            previous_age = int(constraints.get("archive_age_days", 60))
            age_delta = 0 if self.severity == 0.0 else max(1, math.ceil(previous_age * 0.5 * self.severity))
            if age_delta:
                constraints["archive_age_days"] = max(0, previous_age - age_delta)
                deltas["archive_age_days"] = {"before": previous_age, "after": constraints["archive_age_days"]}
            if self.severity >= 0.75:
                previous = constraints.get("protect_hidden", True)
                constraints["protect_hidden"] = False
                deltas["protect_hidden"] = {"before": previous, "after": False}
        elif response.observation.env_name == "calendar_ops":
            previous_end = int(constraints.get("working_hours_end", 17))
            extension = 0 if self.severity == 0.0 else max(1, math.ceil(3 * self.severity))
            if extension:
                constraints["working_hours_end"] = previous_end + extension
                deltas["working_hours_end"] = {"before": previous_end, "after": previous_end + extension}
            if self.severity >= 0.5:
                previous_timezone = constraints.get("timezone")
                constraints["timezone"] = "UTC+00:00"
                deltas["timezone"] = {"before": previous_timezone, "after": "UTC+00:00"}
        elif response.observation.env_name == "risk_ops":
            previous_limit = int(constraints.get("risk_limit", 60))
            limit_delta = 0 if self.severity == 0.0 else max(1, math.ceil(20 * self.severity))
            if limit_delta:
                constraints["risk_limit"] = previous_limit + limit_delta
                deltas["risk_limit"] = {"before": previous_limit, "after": previous_limit + limit_delta}
        effect = self._effect(
            "constraint_delta",
            self.severity if deltas else 0.0,
            {"constraint_deltas": deltas, "changed_constraint_count": len(deltas)},
        )
        return clone_response(response, constraints=constraints, metadata=self._record(response, effect))
