from __future__ import annotations
from abc import ABC, abstractmethod
from src.core.context import ObservationContext
from src.core.types import AgentAction, MonitorDecision, Observation


class BaseMonitor(ABC):
    name = "base_monitor"

    @abstractmethod
    def check(self, context: ObservationContext, observation: Observation, action: AgentAction) -> MonitorDecision:
        raise NotImplementedError
