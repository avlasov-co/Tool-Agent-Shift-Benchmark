from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Mapping, Tuple

from tool_agent_shift_benchmark.core.memory import PolicyMemoryView
from tool_agent_shift_benchmark.core.policy_adapter import BasePolicyAdapter, validate_policy_adapter
from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass
from tool_agent_shift_benchmark.core.types import AgentAction, Observation, ToolResponse

EVALUATOR_ONLY_OBSERVATION_METADATA_KEYS = {
    "faults",
    "fault_schedule_provenance",
    "scenario_split",
    "scenario_family",
}
EVALUATOR_ONLY_RESPONSE_METADATA_KEYS = {"faults", "ground_truth", "score", "labels"}
POLICY_VISIBLE_SCENARIO_ID = "policy_visible_scenario"


def redact_response_for_policy(response: ToolResponse) -> ToolResponse:
    """Return a defensive tool response containing policy-visible data only."""

    observation_metadata = {
        key: value
        for key, value in response.observation.metadata.items()
        if key not in EVALUATOR_ONLY_OBSERVATION_METADATA_KEYS
    }
    response_metadata = {
        key: value for key, value in response.metadata.items() if key not in EVALUATOR_ONLY_RESPONSE_METADATA_KEYS
    }
    return replace(
        response,
        observation=replace(
            response.observation,
            scenario_id=POLICY_VISIBLE_SCENARIO_ID,
            metadata=observation_metadata,
        ),
        metadata=response_metadata,
    )


@dataclass(frozen=True, slots=True)
class ObservationContext:
    """Visible-only context passed to agents and monitors.

    Environment behavior is supplied by a capability-minimal policy adapter.
    The context never retains the environment, evaluator, clean response, or
    execution/hidden-state operations.
    """

    policy_adapter: BasePolicyAdapter
    current_time: int
    observation_timestamp: int
    response_latency_ms: int
    response_received_at: int
    memory: PolicyMemoryView | None = None

    def __post_init__(self) -> None:
        validate_policy_adapter(self.policy_adapter)
        for label, value in (
            ("current_time", self.current_time),
            ("observation_timestamp", self.observation_timestamp),
            ("response_latency_ms", self.response_latency_ms),
            ("response_received_at", self.response_received_at),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"observation context {label} must be an integer")
        if self.response_latency_ms < 0:
            raise ValueError("observation context response latency must be non-negative")

    @classmethod
    def from_policy_adapter(
        cls,
        policy_adapter: BasePolicyAdapter,
        observation: Observation,
        *,
        current_time: int | None = None,
        response_latency_ms: int = 0,
        response_received_at: int | None = None,
        memory: PolicyMemoryView | None = None,
    ) -> "ObservationContext":
        adapter = validate_policy_adapter(policy_adapter)
        if adapter.environment_name != observation.env_name:
            raise ValueError(
                "policy adapter environment does not match the visible observation: "
                f"{adapter.environment_name!r} != {observation.env_name!r}"
            )
        visible_time = observation.timestamp if current_time is None else current_time
        return cls(
            adapter,
            visible_time,
            observation.timestamp,
            response_latency_ms,
            visible_time if response_received_at is None else response_received_at,
            memory,
        )

    @classmethod
    def from_environment(
        cls,
        environment: object,
        observation: Observation,
        *,
        response_latency_ms: int = 0,
        response_received_at: int | None = None,
        memory: PolicyMemoryView | None = None,
    ) -> "ObservationContext":
        """Compatibility constructor; runtime code uses `from_policy_adapter`."""

        adapter_factory = getattr(environment, "policy_adapter", None)
        if not callable(adapter_factory):
            raise TypeError("environment does not provide a policy_adapter")
        adapter = validate_policy_adapter(adapter_factory(observation))
        current_time = int(getattr(environment, "current_time", observation.timestamp))
        return cls.from_policy_adapter(
            adapter,
            observation,
            current_time=current_time,
            response_latency_ms=response_latency_ms,
            response_received_at=response_received_at,
            memory=memory,
        )

    @property
    def env_name(self) -> str:
        return self.policy_adapter.environment_name

    @property
    def required_fields(self) -> Tuple[str, ...]:
        return self.policy_adapter.required_fields

    @property
    def constraints(self) -> Mapping[str, Any]:
        return self.policy_adapter.constraints

    @property
    def task_hint(self) -> str:
        return str(self.policy_adapter.task_metadata.get("task", ""))

    @property
    def task_parameters(self) -> Mapping[str, Any]:
        return self.policy_adapter.task_metadata

    @property
    def action_schema(self) -> Mapping[str, Any]:
        return self.policy_adapter.action_schema

    def visible_candidates(self, observation: Observation) -> tuple[Mapping[str, Any], ...]:
        return self.policy_adapter.visible_candidates(observation)

    def recommended_action(self, data: Dict[str, Any]) -> AgentAction:
        return self.policy_adapter.recommend_action(data)

    def validate_observation_data(self, data: Dict[str, Any]) -> List[str]:
        return list(self.policy_adapter.validate_observation_data(data))

    def validate_action(self, action: AgentAction, observation: Observation | None = None) -> Tuple[bool, List[str]]:
        allowed, reasons = self.policy_adapter.validate_action(action, observation)
        return allowed, list(reasons)

    def abstain(self, reason: str) -> AgentAction:
        return self.policy_adapter.abstain(reason)

    def to_dict(self) -> dict[str, Any]:
        value = {
            "policy_adapter": self.policy_adapter.to_dict(),
            "current_time": self.current_time,
            "observation_timestamp": self.observation_timestamp,
            "response_latency_ms": self.response_latency_ms,
            "response_received_at": self.response_received_at,
            "memory": self.memory.to_dict() if self.memory is not None else None,
        }
        normalized = canonicalize(value)
        if not isinstance(normalized, dict):
            raise RuntimeError("observation context did not serialize to a mapping")
        return normalized


register_dataclass(ObservationContext)
