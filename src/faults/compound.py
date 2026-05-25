from __future__ import annotations
from dataclasses import replace
from random import Random
from .base import BaseFault
from .stale_observation import StaleObservationFault
from .missing_field import MissingFieldFault
from .latency_spike import LatencySpikeFault
from .conflicting_output import ConflictingOutputFault


class CompoundShiftFault(BaseFault):
    name = "compound_shift"

    def __init__(self, severity: float = 1.0):
        super().__init__(severity)
        self.parts = [
            StaleObservationFault(severity),
            MissingFieldFault(severity),
            ConflictingOutputFault(severity),
            LatencySpikeFault(severity),
        ]

    def apply(self, response, env, rng: Random):
        out = response
        for part in self.parts:
            out = part.apply(out, env, rng)
        obs = out.observation
        meta = dict(obs.metadata)
        meta.setdefault("faults", []).append({"name": self.name, "severity": self.severity, "metadata": {"parts": [p.name for p in self.parts]}})
        return replace(out, observation=replace(obs, metadata=meta))
