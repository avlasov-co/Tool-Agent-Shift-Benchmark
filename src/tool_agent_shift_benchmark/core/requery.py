"""Versioned records for policy-requested tool requeries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from tool_agent_shift_benchmark.core.immutability import freeze_mapping
from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass

TOOL_REQUERY_CONTRACT = "tool-requery-v1"
REQUERY_ACTION_TYPE = "requery_tool"
TOOL_CALL_COST_UNITS = 1


@dataclass(frozen=True)
class ToolAttemptRecord:
    contract: str
    step: int
    attempt_number: int
    maximum_attempts: int
    tool_call_id: str
    decision_type: str
    outcome: str
    reason: str
    reasons: tuple[str, ...]
    tool_cost_units: int
    latency_ms: int
    visible_response_hash: str
    response_provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.contract != TOOL_REQUERY_CONTRACT:
            raise ValueError(f"unsupported tool requery contract: {self.contract!r}")
        if self.step < 0 or self.attempt_number <= 0:
            raise ValueError("tool attempt step and attempt number must be non-negative")
        if self.maximum_attempts < self.attempt_number:
            raise ValueError("maximum attempts must cover the recorded attempt")
        if self.tool_cost_units < 0 or self.latency_ms < 0:
            raise ValueError("tool attempt cost and latency must be non-negative")
        object.__setattr__(
            self,
            "response_provenance",
            freeze_mapping(self.response_provenance, path="$.tool_attempt.response_provenance"),
        )

    def to_dict(self) -> dict[str, Any]:
        normalized = canonicalize(self)
        if not isinstance(normalized, dict):
            raise RuntimeError("tool attempt did not normalize to a mapping")
        return normalized

    def policy_dict(self) -> dict[str, Any]:
        """Return attempt data without evaluator-only schedule provenance."""

        value = self.to_dict()
        value.pop("response_provenance")
        return value


register_dataclass(ToolAttemptRecord)
