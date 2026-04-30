from __future__ import annotations
from src.core.types import MonitorDecision
from .base import BaseMonitor


class FreshnessMonitor(BaseMonitor):
    name = "freshness_monitor"

    def __init__(self, max_age: int = 3):
        self.max_age = max_age

    def check(self, env, observation, action):
        age = getattr(env, "current_time", observation.timestamp) - observation.timestamp
        reasons = [f"stale_observation:age={age}"] if age > self.max_age else []
        return MonitorDecision(self.name, not reasons, 0.8 if reasons else 0.0, reasons, {"age": age, "max_age": self.max_age})
