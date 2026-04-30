from __future__ import annotations
from random import Random
from .base import BaseFault, clone_response


class SchemaDriftFault(BaseFault):
    name = "schema_drift"

    def apply(self, response, env, rng: Random):
        data = dict(response.observation.data)
        if "files" in data:
            data["items"] = data.pop("files")
            changed = "files->items"
        elif "availability" in data:
            data["slots"] = data.pop("availability")
            changed = "availability->slots"
        elif "market_state" in data:
            data["snapshot"] = data.pop("market_state")
            changed = "market_state->snapshot"
        else:
            changed = "none"
        meta = dict(response.observation.metadata)
        meta.setdefault("faults", []).append({"name": self.name, "metadata": {"changed": changed}})
        return clone_response(response, data=data, schema_version="v2_drifted", metadata=meta)
