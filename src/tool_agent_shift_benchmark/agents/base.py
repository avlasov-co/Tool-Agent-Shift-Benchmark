from __future__ import annotations

from abc import ABC, abstractmethod

from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.contracts import empty_configuration_schema
from tool_agent_shift_benchmark.core.types import AgentDecision, ToolResponse


class BaseAgent(ABC):
    name = "base_agent"
    version = "1.0.0"
    capabilities: tuple[str, ...] = ()
    configuration_schema = empty_configuration_schema()

    @abstractmethod
    def decide(self, context: ObservationContext, response: ToolResponse) -> AgentDecision:
        raise NotImplementedError
