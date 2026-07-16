from __future__ import annotations

from random import Random

from .base import BaseFault, clone_response


class LatencySpikeFault(BaseFault):
    name = "latency_spike"

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
