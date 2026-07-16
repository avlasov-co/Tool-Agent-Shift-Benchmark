"""Environment-provided, policy-visible adapter contract implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from tool_agent_shift_benchmark.core.immutability import freeze_mapping
from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass
from tool_agent_shift_benchmark.core.types import AgentAction, Observation

ENVIRONMENT_POLICY_ADAPTER_CONTRACT = "environment-policy-adapter-v1"
POLICY_ADAPTER_CAPABILITIES = (
    "action_schema",
    "visible_candidates",
    "visible_validation",
    "safe_abstention",
    "recommendation_helpers",
)


@dataclass(frozen=True, slots=True)
class BasePolicyAdapter:
    """Immutable-data base for environment-specific visible policy behavior.

    Subclasses supply pure methods over these fields and the current visible
    observation. They must not retain an environment or evaluator object.
    """

    environment_name: str
    required_fields: tuple[str, ...]
    constraints: Mapping[str, Any]
    task_metadata: Mapping[str, Any]
    action_schema: Mapping[str, Any]
    capabilities: tuple[str, ...] = POLICY_ADAPTER_CAPABILITIES
    contract_version: str = field(init=False, default=ENVIRONMENT_POLICY_ADAPTER_CONTRACT)

    def __post_init__(self) -> None:
        if not self.environment_name or self.contract_version != ENVIRONMENT_POLICY_ADAPTER_CONTRACT:
            raise ValueError("policy adapter requires a valid environment and contract")
        for label, value in (
            ("constraints", self.constraints),
            ("task_metadata", self.task_metadata),
            ("action_schema", self.action_schema),
        ):
            object.__setattr__(self, label, freeze_mapping(value, path=f"$.policy_adapter.{label}"))
        required = tuple(str(value) for value in self.required_fields)
        if any(not value for value in required) or len(required) != len(set(required)):
            raise ValueError("policy adapter required fields must be unique non-empty strings")
        capabilities = tuple(str(value) for value in self.capabilities)
        if capabilities != POLICY_ADAPTER_CAPABILITIES:
            raise ValueError("policy adapter capabilities must match the public v1 capability set")
        object.__setattr__(self, "required_fields", required)
        object.__setattr__(self, "capabilities", capabilities)

    def visible_candidates(self, observation: Observation) -> tuple[Mapping[str, Any], ...]:
        raise NotImplementedError

    def validate_observation_data(self, data: Mapping[str, Any]) -> tuple[str, ...]:
        raise NotImplementedError

    def validate_action(
        self,
        action: AgentAction,
        observation: Observation | None = None,
    ) -> tuple[bool, tuple[str, ...]]:
        raise NotImplementedError

    def abstain(self, reason: str) -> AgentAction:
        return AgentAction("abstain", abstain=True, reason=reason)

    def recommend_action(self, data: Mapping[str, Any]) -> AgentAction:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "environment_name": self.environment_name,
            "required_fields": list(self.required_fields),
            "constraints": canonicalize(self.constraints),
            "task_metadata": canonicalize(self.task_metadata),
            "action_schema": canonicalize(self.action_schema),
            "capabilities": list(self.capabilities),
        }


def validate_policy_adapter(adapter: object) -> BasePolicyAdapter:
    if not isinstance(adapter, BasePolicyAdapter):
        raise TypeError("environment policy_adapter must return a BasePolicyAdapter")
    for forbidden in (
        "environment",
        "_environment",
        "hidden_ground_truth",
        "execute",
        "tool_response",
        "counterfactual_state",
    ):
        if hasattr(adapter, forbidden):
            raise ValueError(f"policy adapter exposes forbidden capability {forbidden!r}")
    return adapter


register_dataclass(BasePolicyAdapter)
