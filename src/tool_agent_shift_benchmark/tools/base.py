from __future__ import annotations

from abc import ABC, abstractmethod

from tool_agent_shift_benchmark.core.types import ToolResponse


class SyntheticTool(ABC):
    name = "base_tool"

    @abstractmethod
    def call(self) -> ToolResponse:
        raise NotImplementedError
