from __future__ import annotations

from dataclasses import replace
from random import Random

from tool_agent_shift_benchmark.core.fault_composition import compose_fault_chain

from .base import BaseFault
from .conflicting_output import ConflictingOutputFault
from .latency_spike import LatencySpikeFault
from .missing_field import MissingFieldFault
from .stale_observation import StaleObservationFault


class CompoundShiftFault(BaseFault):
    """Deprecated compatibility alias for the historical fixed chain."""

    name = "compound_shift"
    version = "4.0.0"
    channel = "ordered_composition"
    mechanism = "deprecated_alias_to_generic_composition"
    severity_semantics = "shared severity applied to every legacy component"
    schedule_behavior = "applies its fixed chain in declaration order on active calls"
    detection_path = "component-specific detectors"
    adaptation_path = "component-specific adaptations in observed order"
    deprecated = True
    replacement = (
        "stale_observation",
        "missing_field",
        "conflicting_tool_output",
        "latency_spike",
    )

    def __init__(self, severity: float = 1.0):
        super().__init__(severity)
        self.parts = [
            StaleObservationFault(severity),
            MissingFieldFault(severity),
            ConflictingOutputFault(severity),
            LatencySpikeFault(severity),
        ]

    def apply(self, response, env, rng: Random):
        initial_effect_count = len(response.observation.metadata.get("faults", []))
        applications = tuple((part.name, part, rng.getrandbits(63)) for part in self.parts)
        out, composition = compose_fault_chain(
            response,
            env,
            applications,
            schedule_id="deprecated_compound_shift_alias",
            scheduled_severity=self.severity,
        )
        component_effects = list(out.observation.metadata.get("faults", []))[initial_effect_count:]
        realized = max((float(effect["realized_magnitude"]) for effect in component_effects), default=0.0)
        effect = self._effect(
            "compound_effect",
            realized,
            {
                "parts": [part.name for part in self.parts],
                "deprecated_alias": True,
                "replacement_shift_chain": list(self.replacement),
                "composition": composition.to_dict(),
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
