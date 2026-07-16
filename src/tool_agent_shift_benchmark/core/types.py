from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, is_dataclass
from typing import Any, Optional

from tool_agent_shift_benchmark.core.immutability import freeze_mapping
from tool_agent_shift_benchmark.core.memory import MemoryOperation, MemoryWrite
from tool_agent_shift_benchmark.core.requery import REQUERY_ACTION_TYPE
from tool_agent_shift_benchmark.core.serialization import canonical_dumps, canonicalize, register_dataclass
from tool_agent_shift_benchmark.core.serialization import stable_hash as stable_hash


def canonical_json(value: Any) -> str:
    return canonical_dumps(value)


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class FaultConfig:
    name: str
    severity: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty("fault name", self.name)
        if (
            not isinstance(self.severity, (int, float))
            or isinstance(self.severity, bool)
            or not math.isfinite(self.severity)
            or not 0.0 <= self.severity <= 1.0
        ):
            raise ValueError("severity must be finite and in [0, 1]")
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata, path="$.fault.metadata"))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class Observation:
    env_name: str
    scenario_id: str
    timestamp: int
    data: Mapping[str, Any]
    schema_version: str = "v1"
    constraints: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty("env_name", self.env_name)
        _require_non_empty("scenario_id", self.scenario_id)
        if not isinstance(self.timestamp, int):
            raise ValueError("timestamp must be an int")
        for name in ("data", "constraints", "metadata"):
            object.__setattr__(self, name, freeze_mapping(getattr(self, name), path=f"$.observation.{name}"))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ToolResponse:
    tool_name: str
    ok: bool
    observation: Observation
    latency_ms: int = 0
    errors: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty("tool_name", self.tool_name)
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        object.__setattr__(self, "errors", tuple(str(error) for error in self.errors))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata, path="$.tool_response.metadata"))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class AgentAction:
    action_type: str
    target: Optional[str] = None
    params: Mapping[str, Any] = field(default_factory=dict)
    abstain: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        _require_non_empty("action_type", self.action_type)
        if not self.abstain and self.action_type == "abstain":
            object.__setattr__(self, "abstain", True)
        if self.action_type == REQUERY_ACTION_TYPE and (self.abstain or self.target is not None):
            raise ValueError("a tool requery cannot abstain or target an environment resource")
        object.__setattr__(self, "params", freeze_mapping(self.params, path="$.agent_action.params"))

    @property
    def is_requery(self) -> bool:
        return self.action_type == REQUERY_ACTION_TYPE

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class AgentDecision:
    agent_name: str
    action: AgentAction
    confidence: float
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    memory_writes: tuple[MemoryWrite, ...] = ()
    memory_operations: tuple[MemoryOperation, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("agent_name", self.agent_name)
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")
        object.__setattr__(self, "reasons", tuple(str(reason) for reason in self.reasons))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata, path="$.agent_decision.metadata"))
        object.__setattr__(self, "memory_writes", tuple(self.memory_writes))
        object.__setattr__(self, "memory_operations", tuple(self.memory_operations))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class MonitorDecision:
    monitor_name: str
    allow_action: bool
    risk_score: float
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty("monitor_name", self.monitor_name)
        if not 0 <= self.risk_score <= 1:
            raise ValueError("risk_score must be in [0, 1]")
        object.__setattr__(self, "reasons", tuple(str(reason) for reason in self.reasons))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata, path="$.monitor_decision.metadata"))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class MetricRecord:
    env_name: str
    agent_name: str
    fault_name: str
    metrics: Mapping[str, float]
    seed: int
    config: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", freeze_mapping(self.metrics, path="$.metric_record.metrics"))
        object.__setattr__(self, "config", freeze_mapping(self.config, path="$.metric_record.config"))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class FailureCase:
    case_id: str
    episode_id: str
    env_name: str
    agent_name: str
    fault_name: str
    unsafe_reasons: tuple[str, ...]
    trace: Mapping[str, Any]
    seed: int

    def __post_init__(self) -> None:
        _require_non_empty("case_id", self.case_id)
        _require_non_empty("episode_id", self.episode_id)
        object.__setattr__(self, "unsafe_reasons", tuple(str(reason) for reason in self.unsafe_reasons))
        object.__setattr__(self, "trace", freeze_mapping(self.trace, path="$.failure_case.trace"))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    unsafe: bool
    constraint_violation: bool
    stale_data_action: bool
    unsafe_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "unsafe_reasons", tuple(str(reason) for reason in self.unsafe_reasons))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata, path="$.execution_result.metadata"))

    def to_dict(self) -> dict[str, Any]:
        return _record_dict(self)


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    if not is_dataclass(obj):
        raise TypeError("expected dataclass instance")
    return _record_dict(obj)


def _record_dict(value: Any) -> dict[str, Any]:
    normalized = canonicalize(value)
    if not isinstance(normalized, dict):
        raise RuntimeError("record did not normalize to a mapping")
    return normalized


for _serializable_dataclass in (
    FaultConfig,
    Observation,
    ToolResponse,
    AgentAction,
    AgentDecision,
    MonitorDecision,
    MetricRecord,
    FailureCase,
    ExecutionResult,
):
    register_dataclass(_serializable_dataclass)
