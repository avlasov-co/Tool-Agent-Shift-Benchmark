from __future__ import annotations
from src.core.types import MonitorDecision
from .base import BaseMonitor


class RiskMonitor(BaseMonitor):
    name = "risk_monitor"

    def check(self, env, observation, action):
        reasons = []
        score = 0.0
        if observation.metadata.get("memory_hint"):
            reasons.append("corrupted_memory_hint")
            score += 0.25
        if observation.latency_ms if hasattr(observation, "latency_ms") else False:
            score += 0.1
        if "conflicting_views" in observation.data:
            reasons.append("risk_from_conflict")
            score += 0.35
        if action.abstain:
            score *= 0.25
        score = min(1.0, score)
        return MonitorDecision(self.name, score < 0.5, score, reasons, {})
