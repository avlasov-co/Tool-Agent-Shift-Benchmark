from __future__ import annotations
from abc import ABC, abstractmethod
from src.core.types import AgentDecision, ToolResponse


class BaseAgent(ABC):
    name = "base_agent"

    @abstractmethod
    def decide(self, env: object, response: ToolResponse) -> AgentDecision:
        raise NotImplementedError
