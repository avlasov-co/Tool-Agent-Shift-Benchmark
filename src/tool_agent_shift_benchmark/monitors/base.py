from __future__ import annotations

from abc import ABC, abstractmethod

from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.types import AgentAction, MonitorDecision, Observation


class BaseMonitor(ABC):
    name = "base_monitor"

    @abstractmethod
    def check(self, context: ObservationContext, observation: Observation, action: AgentAction) -> MonitorDecision:
        raise NotImplementedError
