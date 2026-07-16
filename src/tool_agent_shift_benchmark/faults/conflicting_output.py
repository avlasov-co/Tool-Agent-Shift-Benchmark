from __future__ import annotations

import math
from random import Random

from .base import BaseFault, clone_response


class ConflictingOutputFault(BaseFault):
    name = "conflicting_tool_output"

    def apply(self, response, env, rng: Random):
        data = dict(response.observation.data)
        source_keys = sorted(data)
        affected_count = (
            0 if self.severity == 0.0 else min(len(source_keys), math.ceil(self.severity * len(source_keys)))
        )
        conflicting_fields = source_keys[:affected_count]
        if affected_count:
            source_b = {key: value for key, value in data.items() if key not in conflicting_fields}
            data["conflicting_views"] = {"source_a": dict(data), "source_b": source_b}
        magnitude = affected_count / len(source_keys) if source_keys else 0.0
        effect = self._effect(
            "conflicting_output",
            magnitude,
            {
                "conflicting_fields": conflicting_fields,
                "conflicting_field_count": affected_count,
                "candidate_field_count": len(source_keys),
                "conflict_fraction": magnitude,
            },
        )
        return clone_response(response, data=data, metadata=self._record(response, effect))
