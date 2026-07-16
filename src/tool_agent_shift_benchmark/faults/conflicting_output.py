from __future__ import annotations

import math
from random import Random
from typing import Any

from tool_agent_shift_benchmark.core.serialization import canonicalize, stable_hash

from .base import BaseFault, clone_response


class ConflictingOutputFault(BaseFault):
    name = "conflicting_tool_output"
    channel = "multi_source_evidence"
    mechanism = "named_snapshot_disagreement_with_asymmetric_reliability"
    severity_semantics = "fraction of scenario-relevant claims contradicted by a less reliable source"
    schedule_behavior = "adds a new pair of named snapshots on each active response"
    detection_path = "compare source IDs, snapshot IDs, reliability, and declared disagreement paths"
    adaptation_path = "prefer corroborated higher-reliability evidence, reobserve, or abstain"

    @staticmethod
    def _claims(data: dict[str, Any], environment: str) -> list[tuple[str, Any, Any]]:
        if environment == "file_ops":
            files = data.get("files")
            if not isinstance(files, list):
                return []
            claims = []
            for index, item in enumerate(files):
                if not isinstance(item, dict):
                    continue
                if "protected" in item:
                    claims.append((f"files[{index}].protected", item["protected"], not bool(item["protected"])))
                if "age_days" in item:
                    claims.append((f"files[{index}].age_days", item["age_days"], int(item["age_days"]) + 90))
            return claims
        if environment == "calendar_ops":
            slots = data.get("availability")
            if not isinstance(slots, list):
                return []
            return [
                (f"availability[{index}].timezone", item.get("timezone"), "UTC+00:00")
                for index, item in enumerate(slots)
                if isinstance(item, dict) and "timezone" in item
            ]
        state = data.get("market_state")
        if environment == "risk_ops" and isinstance(state, dict):
            return [
                ("market_state.volatility", state.get("volatility"), 0.01),
                ("market_state.liquidity", state.get("liquidity"), 1.0),
                ("market_state.snapshot_id", state.get("snapshot_id"), "secondary_snapshot"),
            ]
        return []

    def apply(self, response, env, rng: Random):
        data = canonicalize(response.observation.data)
        if not isinstance(data, dict):
            raise TypeError("observation data must be a mapping")
        claims = self._claims(data, response.observation.env_name)
        conflict_count = 0 if self.severity == 0.0 else min(len(claims), math.ceil(self.severity * len(claims)))
        offset = rng.randrange(len(claims)) if claims else 0
        ordered = claims[offset:] + claims[:offset]
        selected = ordered[:conflict_count]
        if selected:
            primary_values = {path: primary for path, primary, _secondary in selected}
            secondary_values = {path: secondary for path, _primary, secondary in selected}
            primary_snapshot = stable_hash(
                {
                    "source": response.tool_name,
                    "timestamp": response.observation.timestamp,
                    "values": primary_values,
                },
                prefix="snapshot",
            )
            secondary_snapshot = stable_hash(
                {
                    "source": "secondary_cache",
                    "timestamp": response.observation.timestamp - 1,
                    "values": secondary_values,
                },
                prefix="snapshot",
            )
            data["conflicting_views"] = {
                "sources": [
                    {
                        "source_id": response.tool_name,
                        "snapshot_id": primary_snapshot,
                        "reliability": 0.95,
                        "observed_at": response.observation.timestamp,
                        "values": primary_values,
                    },
                    {
                        "source_id": "secondary_cache",
                        "snapshot_id": secondary_snapshot,
                        "reliability": round(max(0.05, 0.85 - self.severity * 0.6), 6),
                        "observed_at": response.observation.timestamp - 1,
                        "values": secondary_values,
                    },
                ],
                "disagreement_paths": [path for path, _primary, _secondary in selected],
            }
        magnitude = conflict_count / len(claims) if claims else 0.0
        effect = self._effect(
            "named_source_conflict",
            magnitude,
            {
                "conflicting_fields": [path for path, _primary, _secondary in selected],
                "conflicting_field_count": conflict_count,
                "candidate_field_count": len(claims),
                "conflict_fraction": magnitude,
                "source_provenance": [
                    {
                        "source_id": source["source_id"],
                        "snapshot_id": source["snapshot_id"],
                        "reliability": source["reliability"],
                    }
                    for source in data.get("conflicting_views", {}).get("sources", [])
                ],
                "asymmetric_reliability": bool(selected),
            },
        )
        return clone_response(response, data=data, metadata=self._record(response, effect))
