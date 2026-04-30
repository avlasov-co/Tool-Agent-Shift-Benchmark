from __future__ import annotations
from src.core.types import MonitorDecision
from .schema import SchemaMonitor
from .freshness import FreshnessMonitor
from .consistency import ConsistencyMonitor
from .constraint import ConstraintMonitor
from .risk import RiskMonitor
from .base import BaseMonitor


class CompositeMonitor(BaseMonitor):
    name = "composite_monitor"

    def __init__(self, monitors=None):
        self.monitors = monitors or [SchemaMonitor(), FreshnessMonitor(), ConsistencyMonitor(), ConstraintMonitor(), RiskMonitor()]

    def check(self, env, observation, action):
        decisions = [m.check(env, observation, action) for m in self.monitors]
        reasons = [r for d in decisions for r in d.reasons]
        allow = all(d.allow_action for d in decisions)
        risk = max([d.risk_score for d in decisions] or [0.0])
        return MonitorDecision(self.name, allow, risk, reasons, {"children": [d.to_dict() for d in decisions]})
