from __future__ import annotations

from abc import ABC, abstractmethod
from src.core.types import ToolResponse


class SyntheticTool(ABC):
    name = "base_tool"

    @abstractmethod
    def call(self) -> ToolResponse:
        raise NotImplementedError
