from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
from typing import Any, Dict, List, Optional
import hashlib
import json


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any, prefix: str = "id") -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class FaultConfig:
    name: str
    severity: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty("fault name", self.name)
        if self.severity < 0:
            raise ValueError("severity must be non-negative")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Observation:
    env_name: str
    scenario_id: str
    timestamp: int
    data: Dict[str, Any]
    schema_version: str = "v1"
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty("env_name", self.env_name)
        _require_non_empty("scenario_id", self.scenario_id)
        if not isinstance(self.timestamp, int):
            raise ValueError("timestamp must be an int")
        if not isinstance(self.data, dict):
            raise ValueError("data must be a dict")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolResponse:
    tool_name: str
    ok: bool
    observation: Observation
    latency_ms: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty("tool_name", self.tool_name)
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentAction:
    action_type: str
    target: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    abstain: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        _require_non_empty("action_type", self.action_type)
        if not self.abstain and self.action_type == "abstain":
            object.__setattr__(self, "abstain", True)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentDecision:
    agent_name: str
    action: AgentAction
    confidence: float
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty("agent_name", self.agent_name)
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MonitorDecision:
    monitor_name: str
    allow_action: bool
    risk_score: float
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty("monitor_name", self.monitor_name)
        if not 0 <= self.risk_score <= 1:
            raise ValueError("risk_score must be in [0, 1]")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetricRecord:
    env_name: str
    agent_name: str
    fault_name: str
    metrics: Dict[str, float]
    seed: int
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FailureCase:
    case_id: str
    episode_id: str
    env_name: str
    agent_name: str
    fault_name: str
    unsafe_reasons: List[str]
    trace: Dict[str, Any]
    seed: int

    def __post_init__(self) -> None:
        _require_non_empty("case_id", self.case_id)
        _require_non_empty("episode_id", self.episode_id)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    unsafe: bool
    constraint_violation: bool
    stale_data_action: bool
    unsafe_reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def dataclass_to_dict(obj: Any) -> Dict[str, Any]:
    if not is_dataclass(obj):
        raise TypeError("expected dataclass instance")
    return asdict(obj)
