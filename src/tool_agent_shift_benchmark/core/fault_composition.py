"""Ordered, auditable composition for every scheduled fault chain."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from tool_agent_shift_benchmark.core.context import redact_response_for_policy
from tool_agent_shift_benchmark.core.serialization import register_dataclass, stable_hash
from tool_agent_shift_benchmark.core.shift_context import ShiftContext
from tool_agent_shift_benchmark.core.types import ToolResponse

FAULT_COMPOSITION_CONTRACT = "fault-composition-v1"


@dataclass(frozen=True)
class FaultComponentRecord:
    """One component application with hashes before and after its mechanism."""

    contract: str
    position: int
    name: str
    channel: str
    configured_severity: float
    rng_seed: int
    input_response_hash: str
    output_response_hash: str
    policy_visible_output_hash: str
    effect_hash: str

    def __post_init__(self) -> None:
        if self.contract != FAULT_COMPOSITION_CONTRACT:
            raise ValueError(f"unsupported fault composition contract: {self.contract!r}")
        if self.position < 0 or not self.name or not self.channel:
            raise ValueError("fault component position, name, and channel must be valid")
        if not math.isfinite(self.configured_severity) or not 0.0 <= self.configured_severity <= 1.0:
            raise ValueError("fault component severity must be finite and in [0, 1]")
        if self.rng_seed < 0:
            raise ValueError("fault component seed must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FaultCompositionRecord:
    """Complete non-commutative history for one active scheduled chain."""

    contract: str
    schedule_id: str
    explicit_order: tuple[str, ...]
    scheduled_severity: float
    canonicalization: str
    initial_response_hash: str
    component_history: tuple[FaultComponentRecord, ...]
    final_response_hash: str
    composition_hash: str

    def __post_init__(self) -> None:
        if self.contract != FAULT_COMPOSITION_CONTRACT:
            raise ValueError(f"unsupported fault composition contract: {self.contract!r}")
        if not self.schedule_id or not self.explicit_order:
            raise ValueError("fault composition schedule and order must be non-empty")
        if tuple(component.name for component in self.component_history) != self.explicit_order:
            raise ValueError("fault component history must preserve the explicit order")
        if tuple(component.position for component in self.component_history) != tuple(range(len(self.explicit_order))):
            raise ValueError("fault component positions must be contiguous and ordered")
        if not math.isfinite(self.scheduled_severity) or not 0.0 <= self.scheduled_severity <= 1.0:
            raise ValueError("scheduled severity must be finite and in [0, 1]")
        if self.canonicalization != "none_order_preserved":
            raise ValueError("unproven commutativity must not canonicalize fault order")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compose_fault_chain(
    response: ToolResponse,
    context: ShiftContext,
    components: Sequence[tuple[str, Any, int]],
    *,
    schedule_id: str,
    scheduled_severity: float,
) -> tuple[ToolResponse, FaultCompositionRecord]:
    """Apply ordinary fault components in exact declaration order.

    Each component owns a local deterministic RNG. No order canonicalization is
    performed because the registered mechanisms are not proven commutative.
    """

    if not components:
        raise ValueError("fault composition requires at least one component")
    initial_hash = stable_hash(response.to_dict(), prefix="response")
    current = response
    history: list[FaultComponentRecord] = []
    for position, (declared_name, fault, rng_seed) in enumerate(components):
        actual_name = str(getattr(fault, "name", ""))
        if not declared_name or declared_name != actual_name:
            raise ValueError(
                f"fault component name mismatch at position {position}: declared {declared_name!r}, got {actual_name!r}"
            )
        input_hash = stable_hash(current.to_dict(), prefix="response")
        initial_effect_count = len(current.observation.metadata.get("faults", ()))
        output = fault.apply(current, context.with_rng_seed(rng_seed))
        component_effects = tuple(output.observation.metadata.get("faults", ()))[initial_effect_count:]
        if not component_effects:
            raise ValueError(f"fault component {declared_name!r} did not record an effect")
        history.append(
            FaultComponentRecord(
                FAULT_COMPOSITION_CONTRACT,
                position,
                declared_name,
                str(getattr(fault, "channel", "tool_response")),
                float(getattr(fault, "severity", scheduled_severity)),
                int(rng_seed),
                input_hash,
                stable_hash(output.to_dict(), prefix="response"),
                stable_hash(redact_response_for_policy(output).to_dict(), prefix="visible"),
                stable_hash(component_effects, prefix="effect"),
            )
        )
        current = output
    payload = {
        "contract": FAULT_COMPOSITION_CONTRACT,
        "schedule_id": schedule_id,
        "explicit_order": tuple(name for name, _, _ in components),
        "scheduled_severity": float(scheduled_severity),
        "canonicalization": "none_order_preserved",
        "initial_response_hash": initial_hash,
        "component_history": tuple(history),
        "final_response_hash": stable_hash(current.to_dict(), prefix="response"),
    }
    record = FaultCompositionRecord(
        **payload,
        composition_hash=stable_hash(payload, prefix="composition"),
    )
    return current, record


register_dataclass(FaultComponentRecord)
register_dataclass(FaultCompositionRecord)
