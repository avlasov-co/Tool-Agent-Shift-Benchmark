"""Causal simulated-time records for tool responses and execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from tool_agent_shift_benchmark.core.serialization import register_dataclass

CAUSAL_LATENCY_CONTRACT = "causal-latency-v1"
SIMULATED_CLOCK_UNIT = "ms"


@dataclass(frozen=True)
class ResponseTiming:
    contract: str
    clock_unit: str
    observation_timestamp: int
    response_latency_ms: int
    environment_clock_before: int
    response_received_at: int

    def __post_init__(self) -> None:
        if self.contract != CAUSAL_LATENCY_CONTRACT:
            raise ValueError(f"unsupported causal latency contract: {self.contract!r}")
        if self.clock_unit != SIMULATED_CLOCK_UNIT:
            raise ValueError(f"unsupported simulated clock unit: {self.clock_unit!r}")
        if self.response_latency_ms < 0:
            raise ValueError("response latency must be non-negative")
        if self.response_received_at - self.environment_clock_before != self.response_latency_ms:
            raise ValueError("response time must equal the pre-response clock plus latency")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


register_dataclass(ResponseTiming)
