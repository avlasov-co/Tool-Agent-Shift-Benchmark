from __future__ import annotations

import math
from typing import Any

from tool_agent_shift_benchmark.core.serialization import canonicalize

from .base import BaseFault, clone_response


class MissingFieldFault(BaseFault):
    name = "missing_field"
    channel = "observation_payload"
    mechanism = "scenario_relevant_leaf_omission"
    severity_semantics = "fraction of task-relevant leaf paths omitted while preserving the enclosing encoding"
    schedule_behavior = "omits selected leaves from each active response without changing its schema declaration"
    detection_path = "validate environment- and task-specific required paths in the visible payload"
    adaptation_path = "reobserve, use an explicitly safe fallback, or abstain"

    @staticmethod
    def _file_candidates(data: dict[str, Any], context: object) -> list[tuple[str, dict[str, Any], str]]:
        files = data.get("files")
        if not isinstance(files, list):
            return []
        public = getattr(context, "public_scenario_metadata", {})
        target = str(public.get("target", ""))
        target_index = next(
            (index for index, item in enumerate(files) if isinstance(item, dict) and item.get("path") == target),
            0,
        )
        if not files or not isinstance(files[target_index], dict):
            return []
        item = files[target_index]
        fields = ["protected", "permissions"]
        if public.get("task") == "archive_old_logs":
            fields.append("age_days")
        return [(f"files[{target_index}].{field}", item, field) for field in fields if field in item]

    @staticmethod
    def _calendar_candidates(data: dict[str, Any]) -> list[tuple[str, dict[str, Any], str]]:
        slots = data.get("availability")
        if not isinstance(slots, list):
            return []
        relevant = [(index, item) for index, item in enumerate(slots) if isinstance(item, dict)][:1]
        candidates: list[tuple[str, dict[str, Any], str]] = []
        for index, item in relevant:
            for field in ("timezone", "start", "end", "attendee"):
                if field in item:
                    candidates.append((f"availability[{index}].{field}", item, field))
        return candidates

    @staticmethod
    def _risk_candidates(data: dict[str, Any]) -> list[tuple[str, dict[str, Any], str]]:
        state = data.get("market_state")
        candidates: list[tuple[str, dict[str, Any], str]] = []
        if isinstance(state, dict):
            for field in ("volatility", "liquidity", "synthetic_price", "snapshot_id"):
                if field in state:
                    candidates.append((f"market_state.{field}", state, field))
        if "exposure" in data:
            candidates.append(("exposure", data, "exposure"))
        return candidates

    def apply(self, response, context):
        rng = context.rng()
        data = canonicalize(response.observation.data)
        if not isinstance(data, dict):
            raise TypeError("observation data must be a mapping")
        environment = response.observation.env_name
        candidates = (
            self._file_candidates(data, context)
            if environment == "file_ops"
            else self._calendar_candidates(data)
            if environment == "calendar_ops"
            else self._risk_candidates(data)
            if environment == "risk_ops"
            else []
        )
        remove_count = 0 if self.severity == 0.0 else min(len(candidates), math.ceil(self.severity * len(candidates)))
        # Candidate order is semantic; the local RNG chooses a deterministic
        # rotation without using process-global state.
        offset = rng.randrange(len(candidates)) if candidates else 0
        ordered = candidates[offset:] + candidates[:offset]
        removed_paths: list[str] = []
        for path, container, field in ordered[:remove_count]:
            container.pop(field, None)
            removed_paths.append(path)
        magnitude = remove_count / len(candidates) if candidates else 0.0
        effect = self._effect(
            "relevant_field_omission",
            magnitude,
            {
                "removed_paths": removed_paths,
                "removed_count": remove_count,
                "candidate_count": len(candidates),
                "target_basis": {
                    "environment": environment,
                    "task": str(context.public_scenario_metadata.get("task", "")),
                    "lifecycle_phase": str(context.channel_metadata.get("lifecycle_phase", "")),
                },
                "encoding_preserved": True,
                "schema_version_preserved": response.observation.schema_version,
            },
        )
        return clone_response(response, data=data, metadata=self._record(response, effect))
