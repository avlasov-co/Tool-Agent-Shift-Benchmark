from __future__ import annotations

from random import Random

from .base import BaseFault, clone_response


class LatencySpikeFault(BaseFault):
    name = "latency_spike"
    channel = "service_time"
    mechanism = "causal_response_delay"
    severity_semantics = "proportion of a deterministic call-local maximum latency"
    schedule_behavior = "advances the environment clock on each active tool call"
    detection_path = "inspect policy-visible response latency and received-at time"
    adaptation_path = "revalidate freshness and execution-time constraints"

    def apply(self, response, env, rng: Random):
        maximum_latency = 500 + rng.randint(0, 50)
        latency = round(maximum_latency * self.severity)
        effect = self._effect(
            "response_latency",
            latency / maximum_latency if maximum_latency else 0.0,
            {
                "added_latency_ms": latency,
                "maximum_latency_ms": maximum_latency,
                "latency_before_ms": response.latency_ms,
                "latency_after_ms": response.latency_ms + latency,
            },
        )
        return clone_response(
            response,
            latency_ms=response.latency_ms + latency,
            metadata=self._record(response, effect),
        )
