from __future__ import annotations
from src.core.types import AgentAction, AgentDecision
from src.monitors.composite import CompositeMonitor
from .base import BaseAgent


class MonitorGatedAgent(BaseAgent):
    name = "monitor_gated"

    def __init__(self, monitor=None):
        self.monitor = monitor or CompositeMonitor()
        self.last_monitor_decision = None

    def decide(self, context, response):
        action = context.recommended_action(response.observation.data)
        decision = self.monitor.check(context, response.observation, action)
        self.last_monitor_decision = decision
        if not decision.allow_action:
            return AgentDecision(self.name, AgentAction("abstain", abstain=True, reason="monitor_blocked"), 0.90, decision.reasons, {"monitor": decision.to_dict()})
        return AgentDecision(self.name, action, 0.75, ["monitor_allowed"], {"monitor": decision.to_dict()})
