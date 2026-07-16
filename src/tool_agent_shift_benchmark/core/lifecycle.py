"""Versioned multi-step lifecycle records shared by built-in environments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from tool_agent_shift_benchmark.core.immutability import freeze_mapping
from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass, register_enum

STEP_LIFECYCLE_CONTRACT = "environment-state-machine-v2"


class StopReason(str, Enum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"
    UNSAFE_ACTION = "unsafe_action"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INVALID_ACTION = "invalid_action"
    ORCHESTRATION_ERROR = "orchestration_error"


@dataclass(frozen=True)
class StateTransition:
    contract: str
    sequence: int
    from_phase: str
    action_type: str
    action_target: str | None
    to_phase: str
    state_revision_before: int
    state_revision_after: int
    observation_timestamp: int
    execution_timestamp: int
    transition_completed: bool
    terminal: bool
    stop_reason: str
    unsafe: bool
    unsafe_reasons: tuple[str, ...]
    consequence: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "unsafe_reasons", tuple(str(reason) for reason in self.unsafe_reasons))
        object.__setattr__(self, "consequence", freeze_mapping(self.consequence, path="$.transition.consequence"))

    def to_dict(self) -> dict[str, Any]:
        normalized = canonicalize(self)
        if not isinstance(normalized, dict):
            raise RuntimeError("state transition did not normalize to a mapping")
        return normalized


register_enum(StopReason)
register_dataclass(StateTransition)
