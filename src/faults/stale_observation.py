from __future__ import annotations
from random import Random
from .base import BaseFault, clone_response


class StaleObservationFault(BaseFault):
    name = "stale_observation"

    def apply(self, response, env, rng: Random):
        data = dict(response.observation.data)
        delta = max(1, int(10 * self.severity))
        if response.observation.env_name == "file_ops" and "files" in data:
            files = [dict(f) for f in data["files"]]
            for f in files:
                if f.get("protected") and f.get("kind") == "tmp":
                    f["protected"] = False
            data["files"] = files
        if response.observation.env_name == "calendar_ops" and "availability" in data:
            slots = [dict(s) for s in data["availability"]]
            slots.append({"attendee": "bob", "start": 10, "end": 11, "timezone": "UTC+01:00"})
            data["availability"] = slots
        if response.observation.env_name == "risk_ops" and "market_state" in data:
            state = dict(data["market_state"])
            state["volatility"] = 0.01
            data["market_state"] = state
        return clone_response(response, data=data, timestamp=response.observation.timestamp - delta, metadata=self._record(response, {"timestamp_delta": delta}))
