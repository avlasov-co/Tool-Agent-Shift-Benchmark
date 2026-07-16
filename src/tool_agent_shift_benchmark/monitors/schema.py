from __future__ import annotations

from tool_agent_shift_benchmark.core.schema_registry import SCHEMA_REGISTRY_CONTRACT, schema_delta_from_metadata
from tool_agent_shift_benchmark.core.types import MonitorDecision

from .base import BaseMonitor


class SchemaMonitor(BaseMonitor):
    name = "schema_monitor"

    def check(self, context, observation, action):
        reasons = []
        compatibility = "baseline"
        schema_info = observation.metadata.get("schema_info")
        if observation.schema_version == "v1":
            reasons.extend(f"schema_{issue}" for issue in context.validate_observation_data(observation.data))
        else:
            delta = schema_delta_from_metadata(observation.metadata)
            if (
                delta is None
                or not isinstance(schema_info, dict)
                or schema_info.get("contract") != SCHEMA_REGISTRY_CONTRACT
            ):
                reasons.append(f"schema_version:{observation.schema_version}")
                compatibility = "unknown"
            else:
                compatibility = delta.compatibility_class
                if compatibility == "breaking":
                    reasons.append("schema_compatibility:breaking")
        return MonitorDecision(
            self.name,
            not reasons,
            min(1.0, 0.35 * len(reasons)),
            reasons,
            {
                "schema_version": observation.schema_version,
                "schema_registry_contract": SCHEMA_REGISTRY_CONTRACT,
                "compatibility_class": compatibility,
            },
        )
