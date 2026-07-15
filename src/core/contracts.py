"""Public, versioned plugin contracts for the benchmark platform.

The contracts deliberately use the repository's small dataclasses.  This keeps
first-party plugins backwards compatible while making the policy/evaluator
boundary explicit for third-party plugins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Any, Protocol

from src.core.context import ObservationContext
from src.core.types import (
    AgentAction,
    AgentDecision,
    ExecutionResult,
    MonitorDecision,
    Observation,
    ToolResponse,
)

CONTRACT_VERSION = "1"


@dataclass(frozen=True)
class PluginDescriptor:
    kind: str
    name: str
    version: str = "1.0.0"
    contract_version: str = CONTRACT_VERSION
    capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in {"agent", "environment", "shift", "monitor", "reporter"}:
            raise ValueError(f"invalid plugin kind: {self.kind}")
        if not self.name or not self.version or not self.contract_version:
            raise ValueError("plugin name, version, and contract_version are required")

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "capabilities": list(self.capabilities)}


@dataclass(frozen=True)
class VisibleObservation:
    response: ToolResponse
    context: ObservationContext


@dataclass(frozen=True)
class AgentPolicyContext:
    observation: VisibleObservation


@dataclass(frozen=True)
class ShiftResult:
    response: ToolResponse
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyTraceVisible:
    """Serializable trace containing only data available to policy code."""

    episode_id: str
    steps: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class EvaluatorTrace:
    """Serializable diagnostic trace kept outside the policy trace."""

    episode_id: str
    steps: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"episode_id": self.episode_id, "steps": list(self.steps)}


class EnvironmentPlugin(Protocol):
    name: str

    def __init__(self, seed: int = 0, scenario_index: int = 0): ...
    def tool_response(self) -> ToolResponse: ...
    def execute(self, action: AgentAction, observed_timestamp: int | None = None) -> ExecutionResult: ...
    def hidden_ground_truth(self) -> dict[str, Any]: ...


class AgentPlugin(Protocol):
    name: str

    def decide(self, context: ObservationContext, response: ToolResponse) -> AgentDecision: ...


class ShiftPlugin(Protocol):
    name: str

    def apply(self, response: ToolResponse, env: object, rng: Random) -> ToolResponse: ...


class MonitorPlugin(Protocol):
    name: str

    def check(self, context: ObservationContext, observation: Observation, action: AgentAction) -> MonitorDecision: ...


class Evaluator(Protocol):
    def score(
        self,
        environment: EnvironmentPlugin,
        action: AgentAction,
        execution: ExecutionResult,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class OrchestrationError:
    episode_id: str
    phase: str
    error_type: str
    message: str
    attempts: int = 1

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()
