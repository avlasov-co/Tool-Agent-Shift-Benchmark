"""Capability-minimal context passed to shift plugins."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from types import MappingProxyType
from typing import Any, Mapping

from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass

SHIFT_CONTEXT_SCHEMA_VERSION = "shift-context-v1"


def _freeze(value: Any) -> Any:
    normalized = canonicalize(value)
    if isinstance(normalized, dict):
        return MappingProxyType({key: _freeze(item) for key, item in normalized.items()})
    if isinstance(normalized, list):
        return tuple(_freeze(item) for item in normalized)
    return normalized


@dataclass(frozen=True, slots=True)
class ShiftContext:
    """Only documented safe data available to a shift implementation."""

    schema_version: str
    step_index: int
    attempt_number: int
    public_scenario_metadata: Mapping[str, Any]
    visible_schema: Mapping[str, Any]
    timing: Mapping[str, Any]
    rng_seed: int
    fault_schedule: Mapping[str, Any]
    channel_metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != SHIFT_CONTEXT_SCHEMA_VERSION:
            raise ValueError(f"unsupported shift context schema: {self.schema_version!r}")
        if self.step_index < 0 or self.rng_seed < 0:
            raise ValueError("shift context step and RNG seed must be non-negative")
        if self.attempt_number < 1:
            raise ValueError("shift context attempt number must be positive")
        for field_name in (
            "public_scenario_metadata",
            "visible_schema",
            "timing",
            "fault_schedule",
            "channel_metadata",
        ):
            frozen = _freeze(getattr(self, field_name))
            if not isinstance(frozen, Mapping):
                raise ValueError(f"shift context {field_name} must be a mapping")
            object.__setattr__(self, field_name, frozen)

    @classmethod
    def create(
        cls,
        *,
        step_index: int,
        attempt_number: int,
        public_scenario_metadata: Mapping[str, Any],
        visible_schema: Mapping[str, Any],
        timing: Mapping[str, Any],
        rng_seed: int,
        fault_schedule: Mapping[str, Any],
        channel_metadata: Mapping[str, Any],
    ) -> "ShiftContext":
        return cls(
            SHIFT_CONTEXT_SCHEMA_VERSION,
            step_index,
            attempt_number,
            public_scenario_metadata,
            visible_schema,
            timing,
            rng_seed,
            fault_schedule,
            channel_metadata,
        )

    def with_rng_seed(self, rng_seed: int) -> "ShiftContext":
        return ShiftContext(
            self.schema_version,
            self.step_index,
            self.attempt_number,
            self.public_scenario_metadata,
            self.visible_schema,
            self.timing,
            rng_seed,
            self.fault_schedule,
            self.channel_metadata,
        )

    def rng(self) -> Random:
        """Return a new deterministic component-local random stream."""

        return Random(self.rng_seed)

    def to_dict(self) -> dict[str, Any]:
        normalized = canonicalize(self)
        if not isinstance(normalized, dict):
            raise RuntimeError("shift context did not serialize to a mapping")
        return normalized


register_dataclass(ShiftContext)
