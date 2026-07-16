from __future__ import annotations

from dataclasses import replace
from random import Random

from .base import BaseFault
from .conflicting_output import ConflictingOutputFault
from .latency_spike import LatencySpikeFault
from .missing_field import MissingFieldFault
from .stale_observation import StaleObservationFault


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
        initial_effect_count = len(response.observation.metadata.get("faults", []))
        for part in self.parts:
            out = part.apply(out, env, rng)
        component_effects = list(out.observation.metadata.get("faults", []))[initial_effect_count:]
        realized = max((float(effect["realized_magnitude"]) for effect in component_effects), default=0.0)
        effect = self._effect(
            "compound_effect",
            realized,
            {
                "parts": [part.name for part in self.parts],
                "component_realized_magnitudes": [
                    {
                        "name": component["name"],
                        "realized_magnitude": component["realized_magnitude"],
                    }
                    for component in component_effects
                ],
            },
        )
        return replace(out, observation=replace(out.observation, metadata=self._record(out, effect)))
