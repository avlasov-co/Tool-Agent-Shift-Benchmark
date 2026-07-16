"""Versioned multi-step lifecycle records shared by built-in environments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from tool_agent_shift_benchmark.core.serialization import register_dataclass, register_enum

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


register_enum(StopReason)
register_dataclass(StateTransition)
