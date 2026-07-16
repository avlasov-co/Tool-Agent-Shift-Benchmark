from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from tool_agent_shift_benchmark.core.counterfactual import PURE_COUNTERFACTUAL_CAPABILITY
from tool_agent_shift_benchmark.core.lifecycle import StopReason
from tool_agent_shift_benchmark.core.seeding import SEED_STREAM_ALGORITHM
from tool_agent_shift_benchmark.core.types import AgentAction, ExecutionResult, ToolResponse

if TYPE_CHECKING:
    from tool_agent_shift_benchmark.core.scenarios import ScenarioFamilyDescriptor, ScenarioSpec


class SyntheticEnvironment(ABC):
    name = "base"
    capabilities = (PURE_COUNTERFACTUAL_CAPABILITY,)
    required_fields: List[str] = []
    scenario_generator_name = "deterministic_synthetic_scenarios"
    scenario_generator_version = "3.0.0"

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
            from tool_agent_shift_benchmark.core.scenarios import split_namespace_for_index

            self.scenario_split = split_namespace_for_index(scenario_index)
            self._scenario_spec = self._build_scenario_spec()
        else:
            self._validate_scenario_reference(scenario_spec, seed, scenario_index)
            self.scenario_split = scenario_spec.split
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
    def pure_action_outcome(
        self,
        action: AgentAction,
        observed_timestamp: int | None = None,
    ) -> ExecutionResult:
        """Predict the action outcome without mutating any environment state."""

        raise NotImplementedError

    @abstractmethod
    def visible_constraints(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def validate_action(self, action: AgentAction, observation: object | None = None) -> Tuple[bool, List[str]]:
        raise NotImplementedError

    def hidden_ground_truth(self) -> Dict[str, Any]:
        return {}

    def advance_time_ms(self, duration_ms: int) -> None:
        """Advance the deterministic environment clock and activate timed state."""

        if not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or duration_ms < 0:
            raise ValueError("duration_ms must be a non-negative integer")
        previous_time = self.current_time
        self.current_time += duration_ms
        self._on_time_advanced(previous_time, self.current_time)

    def _on_time_advanced(self, previous_time: int, current_time: int) -> None:
        """Apply environment-specific state whose activation lies in this interval."""

    def _initialize_lifecycle(self, phases: List[str]) -> None:
        if not phases:
            raise ValueError("environment lifecycle requires at least one phase")
        self.lifecycle_phases = list(phases)
        self.lifecycle_phase = phases[0]
        self.state_revision = 0
        self.terminal = False
        self.stop_reason = ""

    def _advance_lifecycle(self, phase: str) -> None:
        if phase not in self.lifecycle_phases:
            raise ValueError(f"unknown lifecycle phase {phase!r}")
        self.lifecycle_phase = phase
        self.state_revision += 1

    def _finish_lifecycle(self, reason: StopReason) -> None:
        self.terminal = True
        self.stop_reason = reason.value
        self.state_revision += 1

    def visible_lifecycle_state(self) -> Dict[str, Any]:
        return {
            "contract": "environment-state-machine-v2",
            "phase": self.lifecycle_phase,
            "state_revision": self.state_revision,
            "terminal": self.terminal,
        }

    def lifecycle_snapshot(self) -> Dict[str, Any]:
        return {
            **self.visible_lifecycle_state(),
            "stop_reason": self.stop_reason,
            "current_time": self.current_time,
        }

    def lifecycle_status(self) -> Dict[str, Any]:
        return {
            "terminal": self.terminal,
            "stop_reason": self.stop_reason,
            "phase": self.lifecycle_phase,
            "state_revision": self.state_revision,
        }

    def counterfactual_state(self) -> Dict[str, Any]:
        """Return the complete evaluator-visible state used to prove score purity."""

        return {
            "environment": self.name,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "scenario_index": self.scenario_index,
            "scenario_manifest_content_hash": self.scenario_spec.content_hash,
            "lifecycle": self.lifecycle_snapshot(),
            "visible_lifecycle": self.visible_lifecycle_state(),
            "hidden_ground_truth": self.hidden_ground_truth(),
        }

    def mark_budget_exhausted(self) -> None:
        if not self.terminal:
            self._finish_lifecycle(StopReason.BUDGET_EXHAUSTED)

    def _abstention_result(self) -> ExecutionResult:
        self._finish_lifecycle(StopReason.ABSTAINED)
        return ExecutionResult(
            False,
            False,
            False,
            False,
            metadata={"abstained": True, "terminal": True, "stop_reason": self.stop_reason},
        )

    def _invalid_transition_result(self, expected_action: str, actual_action: str) -> ExecutionResult:
        return ExecutionResult(
            False,
            False,
            False,
            False,
            metadata={
                "transition_completed": False,
                "recoverable": True,
                "expected_action": expected_action,
                "actual_action": actual_action,
                "phase": self.lifecycle_phase,
            },
        )

    def public_task_description(self) -> Dict[str, Any]:
        return {"task": str(getattr(self, "task", self.name))}

    def transition_parameters(self) -> Dict[str, Any]:
        return {"initial_time": self.current_time}

    def scenario_family_descriptor(self) -> ScenarioFamilyDescriptor:
        from tool_agent_shift_benchmark.core.scenarios import ScenarioFamilyDescriptor

        task = self.public_task_description()
        return ScenarioFamilyDescriptor.create(
            name=f"{self.name}_parameterized_tasks",
            task_type=str(task.get("task", self.name)),
            hazards=(),
            protected_object_types=(),
            constraint_dimensions=tuple(str(key) for key in self.visible_constraints()),
            temporal_behavior=("multi_step_lifecycle",),
            parameters={"scenario_index": self.scenario_index},
        )

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
            split=self.scenario_split,
            family=self.scenario_family_descriptor(),
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
