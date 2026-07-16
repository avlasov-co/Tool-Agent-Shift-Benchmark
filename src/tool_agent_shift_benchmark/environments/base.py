from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from tool_agent_shift_benchmark.core.seeding import SEED_STREAM_ALGORITHM
from tool_agent_shift_benchmark.core.types import AgentAction, ExecutionResult, ToolResponse

if TYPE_CHECKING:
    from tool_agent_shift_benchmark.core.scenarios import ScenarioSpec


class SyntheticEnvironment(ABC):
    name = "base"
    required_fields: List[str] = []
    scenario_generator_name = "deterministic_synthetic_scenarios"
    scenario_generator_version = "2.0.0"

    def __init__(
        self,
        seed: int = 0,
        scenario_index: int = 0,
        scenario_spec: ScenarioSpec | None = None,
    ):
        self.seed = seed
        self.scenario_index = scenario_index
        self.current_time = 1000 + scenario_index
        self.scenario_id = f"{self.name}_scenario_{scenario_index}"
        if scenario_spec is None:
            self.reset(seed, scenario_index)
            self._scenario_spec = self._build_scenario_spec()
        else:
            self._validate_scenario_reference(scenario_spec, seed, scenario_index)
            self._restore_scenario_spec(scenario_spec)
            self._scenario_spec = scenario_spec

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

    def public_task_description(self) -> Dict[str, Any]:
        return {"task": str(getattr(self, "task", self.name))}

    def transition_parameters(self) -> Dict[str, Any]:
        return {"initial_time": self.current_time}

    @property
    def scenario_spec(self) -> ScenarioSpec:
        return self._scenario_spec

    def _build_scenario_spec(self) -> ScenarioSpec:
        from tool_agent_shift_benchmark.core.scenarios import ScenarioSpec

        response = self.tool_response()
        return ScenarioSpec.create(
            generator_name=self.scenario_generator_name,
            generator_version=self.scenario_generator_version,
            environment=self.name,
            scenario_id=self.scenario_id,
            scenario_index=self.scenario_index,
            scenario_seed=self.seed,
            seed_stream_algorithm=SEED_STREAM_ALGORITHM,
            public_task_description=self.public_task_description(),
            policy_visible_state={
                "timestamp": response.observation.timestamp,
                "data": response.observation.data,
                "schema_version": response.observation.schema_version,
            },
            hidden_evaluator_state=self.hidden_ground_truth(),
            constraints=self.visible_constraints(),
            transition_parameters=self.transition_parameters(),
        )

    def _validate_scenario_reference(self, spec: ScenarioSpec, seed: int, scenario_index: int) -> None:
        expected = (self.name, f"{self.name}_scenario_{scenario_index}", int(scenario_index), int(seed))
        actual = (spec.environment, spec.scenario_id, spec.scenario_index, spec.scenario_seed)
        if actual != expected:
            raise ValueError(f"scenario manifest reference mismatch: expected {expected!r}, got {actual!r}")

    def _restore_scenario_spec(self, spec: ScenarioSpec) -> None:
        raise TypeError(f"environment {self.name!r} does not support scenario-manifest replay")

    def generator_metadata(self) -> Dict[str, Any]:
        return {
            "name": self.scenario_generator_name,
            "version": self.scenario_generator_version,
            "seed": self.seed,
            "scenario_index": self.scenario_index,
        }
