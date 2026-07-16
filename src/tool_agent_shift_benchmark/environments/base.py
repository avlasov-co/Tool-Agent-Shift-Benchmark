from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from tool_agent_shift_benchmark.core.types import AgentAction, ExecutionResult, ToolResponse


class SyntheticEnvironment(ABC):
    name = "base"
    required_fields: List[str] = []
    scenario_generator_name = "deterministic_synthetic_scenarios"
    scenario_generator_version = "2.0.0"

    def __init__(self, seed: int = 0, scenario_index: int = 0):
        self.seed = seed
        self.scenario_index = scenario_index
        self.current_time = 1000 + scenario_index
        self.scenario_id = f"{self.name}_scenario_{scenario_index}"
        self.reset(seed, scenario_index)

    @abstractmethod
    def reset(self, seed: int, scenario_index: int = 0) -> None:
        raise NotImplementedError

    @abstractmethod
    def tool_response(self) -> ToolResponse:
        raise NotImplementedError

    @abstractmethod
    def execute(self, action: AgentAction, observed_timestamp: int | None = None) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def visible_constraints(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def validate_action(self, action: AgentAction, observation: object | None = None) -> Tuple[bool, List[str]]:
        raise NotImplementedError

    def hidden_ground_truth(self) -> Dict[str, Any]:
        return {}

    def generator_metadata(self) -> Dict[str, Any]:
        return {
            "name": self.scenario_generator_name,
            "version": self.scenario_generator_version,
            "seed": self.seed,
            "scenario_index": self.scenario_index,
        }
