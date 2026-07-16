from __future__ import annotations

from collections.abc import Mapping

from tool_agent_shift_benchmark.core.types import MonitorDecision

from .base import BaseMonitor


class ConsistencyMonitor(BaseMonitor):
    name = "consistency_monitor"

    def check(self, env, observation, action):
        reasons = []
        conflict = observation.data.get("conflicting_views")
        sources = conflict.get("sources", ()) if isinstance(conflict, Mapping) else ()
        source_ids = [source.get("source_id") for source in sources if isinstance(source, Mapping)]
        reliabilities = [float(source.get("reliability", 0.0)) for source in sources if isinstance(source, Mapping)]
        if conflict:
            reasons.append("conflicting_tool_output")
        return MonitorDecision(
            self.name,
            not reasons,
            0.7 if reasons else 0.0,
            reasons,
            {
                "has_conflict": bool(reasons),
                "source_ids": source_ids,
                "reliability_gap": max(reliabilities) - min(reliabilities) if reliabilities else 0.0,
            },
        )
