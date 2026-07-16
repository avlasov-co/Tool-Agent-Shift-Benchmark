"""Typed declarations for causally distinct fault channels."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from tool_agent_shift_benchmark.core.serialization import register_dataclass

FAULT_CHANNEL_CONTRACT = "fault-channel-v1"
FAULT_CHANNELS = frozenset(
    {
        "none",
        "tool_schema",
        "observation_time",
        "service_time",
        "observation_payload",
        "multi_source_evidence",
        "policy_memory",
        "constraint_visibility",
        "ordered_composition",
    }
)


@dataclass(frozen=True)
class FaultChannelDescriptor:
    contract: str
    fault_name: str
    channel: str
    causal_mechanism: str
    severity_semantics: str
    schedule_behavior: str
    detection_path: str
    adaptation_path: str

    def __post_init__(self) -> None:
        if self.contract != FAULT_CHANNEL_CONTRACT:
            raise ValueError(f"unsupported fault-channel contract: {self.contract!r}")
        if self.channel not in FAULT_CHANNELS:
            raise ValueError(f"unknown fault channel: {self.channel!r}")
        for field in (
            self.fault_name,
            self.causal_mechanism,
            self.severity_semantics,
            self.schedule_behavior,
            self.detection_path,
            self.adaptation_path,
        ):
            if not field:
                raise ValueError("fault-channel descriptor strings must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


register_dataclass(FaultChannelDescriptor)
