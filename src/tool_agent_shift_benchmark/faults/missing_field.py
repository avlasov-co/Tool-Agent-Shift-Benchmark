from __future__ import annotations

import math
from random import Random

from .base import BaseFault, clone_response


class MissingFieldFault(BaseFault):
    name = "missing_field"

    def apply(self, response, env, rng: Random):
        data = dict(response.observation.data)
        removals: list[tuple[str, int | None, str]] = []
        if response.observation.env_name == "file_ops" and "files" in data:
            files = [dict(f) for f in data["files"]]
            for field in ("protected", "permissions", "age_days"):
                removals.extend((f"files[{index}].{field}", index, field) for index in range(len(files)))
        elif response.observation.env_name == "calendar_ops":
            files = []
            removals = [("availability", None, "availability"), ("attendees", None, "attendees")]
        elif response.observation.env_name == "risk_ops":
            files = []
            removals = [
                ("market_state.volatility", None, "volatility"),
                ("market_state.synthetic_price", None, "synthetic_price"),
                ("market_state.liquidity", None, "liquidity"),
                ("market_state.snapshot_id", None, "snapshot_id"),
                ("exposure", None, "exposure"),
            ]
        else:
            files = []
        remove_count = 0 if self.severity == 0.0 else min(len(removals), math.ceil(self.severity * len(removals)))
        removed_paths: list[str] = []
        for path, index, field in removals[:remove_count]:
            if response.observation.env_name == "file_ops" and index is not None:
                files[index].pop(field, None)
            elif response.observation.env_name == "risk_ops" and field != "exposure":
                state = dict(data.get("market_state", {}))
                state.pop(field, None)
                data["market_state"] = state
            else:
                data.pop(field, None)
            removed_paths.append(path)
        if response.observation.env_name == "file_ops" and "files" in data:
            data["files"] = files
        magnitude = remove_count / len(removals) if removals else 0.0
        effect = self._effect(
            "removed_fields",
            magnitude,
            {
                "removed_paths": removed_paths,
                "removed_count": remove_count,
                "candidate_count": len(removals),
            },
        )
        return clone_response(response, data=data, metadata=self._record(response, effect))
