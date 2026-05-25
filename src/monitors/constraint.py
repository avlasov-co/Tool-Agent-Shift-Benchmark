from __future__ import annotations
from src.core.types import MonitorDecision
from .base import BaseMonitor


class ConstraintMonitor(BaseMonitor):
    name = "constraint_monitor"

    def check(self, context, observation, action):
        ok, reasons = context.validate_action(action, observation)
        reasons = [f"constraint:{r}" for r in reasons]
        return MonitorDecision(self.name, ok, min(1.0, 0.4 * len(reasons)), reasons, {"action_type": action.action_type})
