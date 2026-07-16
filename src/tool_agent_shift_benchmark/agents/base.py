from __future__ import annotations

from abc import ABC, abstractmethod

from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.types import AgentDecision, ToolResponse


class BaseAgent(ABC):
    name = "base_agent"

    @abstractmethod
    def decide(self, context: ObservationContext, response: ToolResponse) -> AgentDecision:
        raise NotImplementedError
