from __future__ import annotations
from random import Random
from .base import BaseFault, clone_response


class ConflictingOutputFault(BaseFault):
    name = "conflicting_tool_output"

    def apply(self, response, env, rng: Random):
        data = dict(response.observation.data)
        conflict = {"source_a": dict(data), "source_b": {}}
        if response.observation.env_name == "file_ops":
            conflict["source_b"] = {"files": []}
        elif response.observation.env_name == "calendar_ops":
            conflict["source_b"] = {"availability": [{"attendee": "alice", "start": 10, "end": 11, "timezone": "UTC+01:00"}]}
        elif response.observation.env_name == "risk_ops":
            conflict["source_b"] = {"market_state": {"synthetic_price": 100, "volatility": 0.99, "snapshot_id": "conflict"}, "exposure": data.get("exposure")}
        data["conflicting_views"] = conflict
        meta = dict(response.observation.metadata)
        meta.setdefault("faults", []).append({"name": self.name, "metadata": {"conflict": True}})
        return clone_response(response, data=data, metadata=meta)
