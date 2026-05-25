from __future__ import annotations
from src.core.types import MonitorDecision
from .base import BaseMonitor


class ConsistencyMonitor(BaseMonitor):
    name = "consistency_monitor"

    def check(self, env, observation, action):
        reasons = []
        if "conflicting_views" in observation.data:
            reasons.append("conflicting_tool_output")
        return MonitorDecision(self.name, not reasons, 0.7 if reasons else 0.0, reasons, {"has_conflict": bool(reasons)})
