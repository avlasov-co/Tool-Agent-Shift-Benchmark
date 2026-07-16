from __future__ import annotations

import math
from dataclasses import replace
from random import Random
from typing import Any

from tool_agent_shift_benchmark.core.fault_effects import FAULT_EFFECT_CONTRACT, FaultEffect
from tool_agent_shift_benchmark.core.types import ToolResponse


class BaseFault:
    name = "normal"
    version = "2.0.0"
    capabilities = (FAULT_EFFECT_CONTRACT,)

    def __init__(self, severity: float = 1.0):
        if not isinstance(severity, (int, float)) or isinstance(severity, bool):
            raise ValueError("fault severity must be numeric")
        normalized = float(severity)
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ValueError("fault severity must be finite and in [0, 1]")
        self.severity = normalized

    def _effect(
        self,
        effect_type: str,
        realized_magnitude: float,
        details: dict[str, Any] | None = None,
    ) -> FaultEffect:
        return FaultEffect(
            FAULT_EFFECT_CONTRACT,
            self.name,
            self.severity,
            float(realized_magnitude),
            effect_type,
            realized_magnitude == 0.0,
            details or {},
        )

    def _record(self, response: ToolResponse, effect: FaultEffect) -> dict[str, Any]:
        meta = dict(response.observation.metadata)
        effects = list(meta.get("faults", []))
        effects.append(effect.to_dict())
        meta["faults"] = effects
        return meta

    def _record_only(self, response: ToolResponse, effect: FaultEffect) -> ToolResponse:
        return replace(response, observation=replace(response.observation, metadata=self._record(response, effect)))

    def apply(self, response: ToolResponse, env: object, rng: Random) -> ToolResponse:
        return self._record_only(response, self._effect("no_fault", 0.0, {"reason": "normal_channel"}))


def clone_response(
    response: ToolResponse,
    *,
    data=None,
    constraints=None,
    timestamp=None,
    schema_version=None,
    latency_ms=None,
    metadata=None,
) -> ToolResponse:
    obs = response.observation
    new_obs = replace(
        obs,
        data=dict(obs.data if data is None else data),
        constraints=dict(obs.constraints if constraints is None else constraints),
        timestamp=obs.timestamp if timestamp is None else timestamp,
        schema_version=obs.schema_version if schema_version is None else schema_version,
        metadata=dict(obs.metadata if metadata is None else metadata),
    )
    return replace(
        response,
        observation=new_obs,
        latency_ms=response.latency_ms if latency_ms is None else latency_ms,
    )


class NoFault(BaseFault):
    name = "normal"
