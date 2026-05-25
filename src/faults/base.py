from __future__ import annotations

from dataclasses import replace
from random import Random
from typing import Any
from src.core.types import ToolResponse


class BaseFault:
    name = "normal"

    def __init__(self, severity: float = 1.0):
        self.severity = max(0.0, float(severity))

    def _record(self, response: ToolResponse, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        meta = dict(response.observation.metadata)
        meta.setdefault("faults", []).append({"name": self.name, "severity": self.severity, "metadata": metadata or {}})
        return meta

    def apply(self, response: ToolResponse, env: object, rng: Random) -> ToolResponse:
        obs = response.observation
        return replace(response, observation=replace(obs, metadata=self._record(response)))


def clone_response(response: ToolResponse, *, data=None, constraints=None, timestamp=None, schema_version=None, latency_ms=None, metadata=None) -> ToolResponse:
    obs = response.observation
    new_obs = replace(
        obs,
        data=dict(obs.data if data is None else data),
        constraints=dict(obs.constraints if constraints is None else constraints),
        timestamp=obs.timestamp if timestamp is None else timestamp,
        schema_version=obs.schema_version if schema_version is None else schema_version,
        metadata=dict(obs.metadata if metadata is None else metadata),
    )
    return replace(response, observation=new_obs, latency_ms=response.latency_ms if latency_ms is None else latency_ms)


class NoFault(BaseFault):
    name = "normal"
