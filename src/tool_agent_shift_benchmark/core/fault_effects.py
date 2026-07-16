"""Canonical configured-versus-realized fault effect records."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass

FAULT_EFFECT_CONTRACT = "fault-effect-v1"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in sorted(value.items())})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class FaultEffect:
    contract: str
    name: str
    configured_severity: float
    realized_magnitude: float
    effect_type: str
    no_op: bool
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.contract != FAULT_EFFECT_CONTRACT:
            raise ValueError(f"unsupported fault effect contract: {self.contract!r}")
        if not self.name or not self.effect_type:
            raise ValueError("fault effect name and type must be non-empty")
        for label, value in (
            ("configured severity", self.configured_severity),
            ("realized magnitude", self.realized_magnitude),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{label} must be finite and in [0, 1]")
        if self.no_op != (self.realized_magnitude == 0.0):
            raise ValueError("fault effect no_op must agree with realized magnitude")
        normalized = canonicalize(self.details, path="$.details")
        object.__setattr__(self, "details", _freeze(normalized))

    def to_dict(self) -> dict[str, Any]:
        normalized = canonicalize(self)
        if not isinstance(normalized, dict):
            raise RuntimeError("fault effect did not normalize to a mapping")
        return normalized


register_dataclass(FaultEffect)
