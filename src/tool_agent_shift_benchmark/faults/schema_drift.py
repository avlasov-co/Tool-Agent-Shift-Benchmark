from __future__ import annotations

from dataclasses import replace

from tool_agent_shift_benchmark.core.schema_registry import (
    SCHEMA_CHANGE_FAMILIES,
    SCHEMA_REGISTRY,
    SCHEMA_REGISTRY_CONTRACT,
    apply_schema_delta,
)

from .base import BaseFault, clone_response


class SchemaDriftFault(BaseFault):
    name = "schema_drift"
    version = "4.0.0"
    channel = "tool_schema"
    mechanism = "versioned_schema_delta"
    severity_semantics = "monotonic count of compatible through breaking schema changes"
    schedule_behavior = "applies one declared source-to-target delta at each active tool call"
    detection_path = "validate tool-schema-registry-v1 schema_info and delta hash"
    adaptation_path = "deterministic reverse migration or explicit fail-closed abstention"
    capabilities = (*BaseFault.capabilities, SCHEMA_REGISTRY_CONTRACT)

    def __init__(self, severity: float = 1.0, family: str | None = None):
        super().__init__(severity)
        if family is not None and family not in SCHEMA_CHANGE_FAMILIES:
            raise ValueError(f"unknown schema change family: {family!r}")
        self.family = family

    def apply(self, response, context):
        rng = context.rng()
        if self.severity == 0.0:
            return self._record_only(
                response,
                self._effect(
                    "schema_delta",
                    0.0,
                    {
                        "schema_changed": False,
                        "source_schema": response.observation.schema_version,
                        "target_schema": response.observation.schema_version,
                        "change_families": [],
                        "change_count": 0,
                        "compatibility_class": "compatible",
                        "renamed_fields": [],
                    },
                ),
            )
        families = (self.family,) if self.family is not None else None
        delta = SCHEMA_REGISTRY.delta(
            response.observation.env_name,
            severity=self.severity,
            rng=rng,
            families=families,
        )
        data = apply_schema_delta(response.observation.data, delta)
        renamed = [
            f"{change.source_path}->{change.target_path}"
            for change in delta.changes
            if change.family in {"alias_rename", "nested_field_move"}
        ]
        effect = self._effect(
            "schema_delta",
            len(delta.changes) / len(SCHEMA_CHANGE_FAMILIES),
            {
                "schema_changed": True,
                "source_schema": delta.source_schema.version,
                "target_schema": delta.target_schema.version,
                "schema_delta_hash": delta.delta_hash,
                "change_families": [change.family for change in delta.changes],
                "change_count": len(delta.changes),
                "maximum_change_count": len(SCHEMA_CHANGE_FAMILIES),
                "compatibility_class": delta.compatibility_class,
                "renamed_fields": renamed,
            },
        )
        schema_info = {
            "contract": SCHEMA_REGISTRY_CONTRACT,
            "source_schema": delta.source_schema.to_dict(),
            "target_schema": delta.target_schema.to_dict(),
            "schema_delta": delta.to_dict(),
            "compatibility_class": delta.compatibility_class,
        }
        observation_metadata = self._record(response, effect)
        observation_metadata["schema_info"] = schema_info
        shifted = clone_response(
            response,
            data=data,
            schema_version=delta.target_schema.version,
            metadata=observation_metadata,
        )
        return replace(shifted, metadata={**response.metadata, "schema_info": schema_info})
