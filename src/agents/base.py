from __future__ import annotations
from abc import ABC, abstractmethod
from src.core.context import ObservationContext
from src.core.types import AgentDecision, ToolResponse


class BaseAgent(ABC):
    name = "base_agent"

    @abstractmethod
    def decide(self, context: ObservationContext, response: ToolResponse) -> AgentDecision:
        raise NotImplementedError
