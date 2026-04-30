from __future__ import annotations
from src.core.types import MonitorDecision
from .base import BaseMonitor


class SchemaMonitor(BaseMonitor):
    name = "schema_monitor"

    def check(self, env, observation, action):
        reasons = []
        for field in getattr(env, "required_fields", []):
            if field not in observation.data:
                reasons.append(f"schema_missing:{field}")
        if observation.schema_version != "v1":
            reasons.append(f"schema_version:{observation.schema_version}")
        return MonitorDecision(self.name, not reasons, min(1.0, 0.35 * len(reasons)), reasons, {"schema_version": observation.schema_version})
