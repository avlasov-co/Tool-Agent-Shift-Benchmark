from __future__ import annotations

from random import Random

from .base import BaseFault, clone_response


class SchemaDriftFault(BaseFault):
    name = "schema_drift"

    def apply(self, response, env, rng: Random):
        if self.severity == 0.0:
            return self._record_only(
                response,
                self._effect("schema_incompatibility", 0.0, {"renamed_fields": [], "schema_changed": False}),
            )
        data = dict(response.observation.data)
        primary_mapping = {
            "file_ops": ("files", "items"),
            "calendar_ops": ("availability", "slots"),
            "risk_ops": ("market_state", "snapshot"),
        }
        candidates = [primary_mapping.get(response.observation.env_name), ("lifecycle", "workflow")]
        present = [candidate for candidate in candidates if candidate is not None and candidate[0] in data]
        rename_count = int(self.severity * len(present))
        renamed_fields: list[str] = []
        for source, destination in present[:rename_count]:
            data[destination] = data.pop(source)
            renamed_fields.append(f"{source}->{destination}")
        effect = self._effect(
            "schema_incompatibility",
            self.severity,
            {
                "schema_changed": True,
                "schema_version_before": response.observation.schema_version,
                "schema_version_after": "v2_drifted",
                "renamed_fields": renamed_fields,
                "rename_fraction": rename_count / len(present) if present else 0.0,
            },
        )
        return clone_response(
            response,
            data=data,
            schema_version="v2_drifted",
            metadata=self._record(response, effect),
        )
