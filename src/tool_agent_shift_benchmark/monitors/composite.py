from __future__ import annotations

from tool_agent_shift_benchmark.core.monitoring import monitor_composition
from tool_agent_shift_benchmark.core.schema_registry import SCHEMA_REGISTRY_CONTRACT
from tool_agent_shift_benchmark.core.types import MonitorDecision

from .base import BaseMonitor
from .consistency import ConsistencyMonitor
from .constraint import ConstraintMonitor
from .freshness import FreshnessMonitor
from .risk import RiskMonitor
from .schema import SchemaMonitor


class CompositeMonitor(BaseMonitor):
    name = "composite_monitor"
    version = "2.0.0"
    capabilities = (SCHEMA_REGISTRY_CONTRACT,)

    def __init__(self, monitors=None, *, mode: str = "full_composite_monitor"):
        descriptor = monitor_composition(mode)
        available = {
            "schema_monitor": SchemaMonitor,
            "freshness_monitor": FreshnessMonitor,
            "consistency_monitor": ConsistencyMonitor,
            "constraint_monitor": ConstraintMonitor,
            "risk_monitor": RiskMonitor,
        }
        self.mode = mode
        self.composition = descriptor
        self.monitors = (
            list(monitors) if monitors is not None else [available[component]() for component in descriptor.components]
        )

    def check(self, context, observation, action):
        decisions = [m.check(context, observation, action) for m in self.monitors]
        reasons = [r for d in decisions for r in d.reasons]
        allow = all(d.allow_action for d in decisions)
        risk = max([d.risk_score for d in decisions] or [0.0])
        return MonitorDecision(
            self.mode,
            allow,
            risk,
            reasons,
            {
                "contract": self.composition.contract,
                "mode": self.mode,
                "ordered_components": list(self.composition.components),
                "children": [d.to_dict() for d in decisions],
            },
        )
