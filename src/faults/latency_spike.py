from __future__ import annotations
from random import Random
from .base import BaseFault, clone_response


class LatencySpikeFault(BaseFault):
    name = "latency_spike"

    def apply(self, response, env, rng: Random):
        latency = int((500 + rng.randint(0, 50)) * max(0.1, self.severity))
        return clone_response(response, latency_ms=response.latency_ms + latency, metadata=self._record(response, {"latency_ms": latency}))
