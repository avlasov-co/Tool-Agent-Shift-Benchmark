"""Named monitor compositions used as explicit experimental treatments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from tool_agent_shift_benchmark.core.serialization import register_dataclass

MONITOR_COMPOSITION_CONTRACT = "monitor-composition-v1"
MONITOR_MODE_ORDER = (
    "no_monitor",
    "schema_only",
    "schema_plus_freshness",
    "schema_plus_freshness_plus_consistency",
    "full_composite_monitor",
)
MONITOR_MODES = frozenset(MONITOR_MODE_ORDER)
_COMPONENTS = {
    "no_monitor": (),
    "schema_only": ("schema_monitor",),
    "schema_plus_freshness": ("schema_monitor", "freshness_monitor"),
    "schema_plus_freshness_plus_consistency": (
        "schema_monitor",
        "freshness_monitor",
        "consistency_monitor",
    ),
    "full_composite_monitor": (
        "schema_monitor",
        "freshness_monitor",
        "consistency_monitor",
        "constraint_monitor",
        "risk_monitor",
    ),
}


@dataclass(frozen=True)
class MonitorCompositionDescriptor:
    contract: str
    name: str
    components: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract != MONITOR_COMPOSITION_CONTRACT:
            raise ValueError(f"unsupported monitor composition contract: {self.contract!r}")
        if self.name not in MONITOR_MODES:
            raise ValueError(f"unknown monitor mode: {self.name!r}")
        if self.components != _COMPONENTS[self.name]:
            raise ValueError(f"monitor composition does not match registered mode {self.name!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def monitor_composition(mode: str) -> MonitorCompositionDescriptor:
    if mode not in MONITOR_MODES:
        raise ValueError(f"unknown monitor mode: {mode!r}")
    return MonitorCompositionDescriptor(MONITOR_COMPOSITION_CONTRACT, mode, _COMPONENTS[mode])


def resolve_monitor_modes(requested: Iterable[str]) -> tuple[str, ...]:
    values = tuple(str(value) for value in requested)
    unknown = set(values) - MONITOR_MODES
    if unknown:
        raise ValueError(f"unknown monitor mode: {sorted(unknown)[0]!r}")
    if len(values) != len(set(values)):
        raise ValueError("monitor modes must not contain duplicates")
    selected = set(values or ("full_composite_monitor",))
    return tuple(mode for mode in MONITOR_MODE_ORDER if mode in selected)


register_dataclass(MonitorCompositionDescriptor)
