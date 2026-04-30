from __future__ import annotations
from abc import ABC, abstractmethod
from src.core.types import AgentAction, MonitorDecision, Observation


class BaseMonitor(ABC):
    name = "base_monitor"

    @abstractmethod
    def check(self, env: object, observation: Observation, action: AgentAction) -> MonitorDecision:
        raise NotImplementedError
