from __future__ import annotations

from tool_agent_shift_benchmark.core.types import MonitorDecision

from .base import BaseMonitor


class RiskMonitor(BaseMonitor):
    name = "risk_monitor"

    def check(self, context, observation, action):
        reasons = []
        score = 0.0
        if observation.metadata.get("memory_hint"):
            reasons.append("corrupted_memory_hint")
            score += 0.25
        latency_risk = min(0.4, context.response_latency_ms / 2000)
        if context.response_latency_ms:
            reasons.append(f"response_latency_ms:{context.response_latency_ms}")
            score += latency_risk
        if "conflicting_views" in observation.data:
            reasons.append("risk_from_conflict")
            score += 0.35
        if action.abstain:
            score *= 0.25
        score = min(1.0, score)
        return MonitorDecision(
            self.name,
            score < 0.5,
            score,
            reasons,
            {
                "response_latency_ms": context.response_latency_ms,
                "response_received_at": context.response_received_at,
                "latency_risk": latency_risk,
            },
        )
