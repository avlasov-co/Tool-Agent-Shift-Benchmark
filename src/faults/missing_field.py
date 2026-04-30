from __future__ import annotations
from random import Random
from .base import BaseFault, clone_response


class MissingFieldFault(BaseFault):
    name = "missing_field"

    def apply(self, response, env, rng: Random):
        data = dict(response.observation.data)
        if response.observation.env_name == "file_ops" and "files" in data:
            files = [dict(f) for f in data["files"]]
            for f in files:
                f.pop("protected", None)
            data["files"] = files
            removed = "files[].protected"
        elif response.observation.env_name == "calendar_ops":
            data.pop("availability", None)
            removed = "availability"
        elif response.observation.env_name == "risk_ops":
            state = dict(data.get("market_state", {}))
            state.pop("volatility", None)
            data["market_state"] = state
            removed = "market_state.volatility"
        else:
            removed = "unknown"
        meta = dict(response.observation.metadata)
        meta.setdefault("faults", []).append({"name": self.name, "metadata": {"removed": removed}})
        return clone_response(response, data=data, metadata=meta)
