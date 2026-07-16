from __future__ import annotations

from tool_agent_shift_benchmark.core.types import MonitorDecision

from .base import BaseMonitor


class FreshnessMonitor(BaseMonitor):
    name = "freshness_monitor"

    def __init__(self, max_age: int = 3):
        self.max_age = max_age

    def check(self, context, observation, action):
        age = context.current_time - observation.timestamp
        reasons = [f"stale_observation:age={age}"] if age > self.max_age else []
        return MonitorDecision(
            self.name,
            not reasons,
            0.8 if reasons else 0.0,
            reasons,
            {
                "age": age,
                "max_age": self.max_age,
                "response_latency_ms": context.response_latency_ms,
                "response_received_at": context.response_received_at,
            },
        )
