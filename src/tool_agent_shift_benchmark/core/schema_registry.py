"""Versioned tool-schema registry and deterministic migration support."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from random import Random
from typing import Any, Iterable, Mapping

from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass, stable_hash

SCHEMA_REGISTRY_CONTRACT = "tool-schema-registry-v1"
SCHEMA_CHANGE_FAMILIES = (
    "additive_field",
    "type_widening",
    "alias_rename",
    "nested_field_move",
    "unit_change",
    "required_field_removal",
    "breaking_type_change",
)


@dataclass(frozen=True)
class SchemaField:
    path: str
    value_type: str
    required: bool
    unit: str | None = None


@dataclass(frozen=True)
class ToolSchema:
    contract: str
    environment: str
    version: str
    fields: tuple[SchemaField, ...]
    schema_hash: str

    @classmethod
    def create(cls, environment: str, version: str, fields: Iterable[SchemaField]) -> "ToolSchema":
        ordered = tuple(sorted(fields, key=lambda field: field.path))
        payload = {
            "contract": SCHEMA_REGISTRY_CONTRACT,
            "environment": environment,
            "version": version,
            "fields": [asdict(field) for field in ordered],
        }
        return cls(
            SCHEMA_REGISTRY_CONTRACT,
            environment,
            version,
            ordered,
            stable_hash(payload, prefix="schema"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SchemaChange:
    family: str
    source_path: str | None
    target_path: str | None
    source_type: str | None
    target_type: str | None
    source_unit: str | None = None
    target_unit: str | None = None
    compatibility: str = "compatible"

    def __post_init__(self) -> None:
        if self.family not in SCHEMA_CHANGE_FAMILIES:
            raise ValueError(f"unknown schema change family: {self.family!r}")
        if self.compatibility not in {"compatible", "requires_adaptation", "breaking"}:
            raise ValueError(f"unknown schema compatibility: {self.compatibility!r}")


@dataclass(frozen=True)
class SchemaDelta:
    contract: str
    source_schema: ToolSchema
    target_schema: ToolSchema
    changes: tuple[SchemaChange, ...]
    compatibility_class: str
    delta_hash: str

    @classmethod
    def create(
        cls,
        source_schema: ToolSchema,
        target_schema: ToolSchema,
        changes: Iterable[SchemaChange],
    ) -> "SchemaDelta":
        ordered = tuple(changes)
        classes = {change.compatibility for change in ordered}
        compatibility = (
            "breaking"
            if "breaking" in classes
            else "requires_adaptation"
            if "requires_adaptation" in classes
            else "compatible"
        )
        payload = {
            "contract": SCHEMA_REGISTRY_CONTRACT,
            "source_schema": source_schema.to_dict(),
            "target_schema": target_schema.to_dict(),
            "changes": [asdict(change) for change in ordered],
            "compatibility_class": compatibility,
        }
        return cls(
            SCHEMA_REGISTRY_CONTRACT,
            source_schema,
            target_schema,
            ordered,
            compatibility,
            stable_hash(payload, prefix="schema_delta"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SchemaAdaptationResult:
    status: str
    data: dict[str, Any]
    repairs: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def succeeded(self) -> bool:
        return self.status in {"compatible", "repaired"}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _baseline_fields(environment: str) -> tuple[SchemaField, ...]:
    common = (
        SchemaField("lifecycle", "object", True),
        SchemaField("lifecycle.phase", "string", True),
        SchemaField("lifecycle.state_revision", "integer", True),
        SchemaField("lifecycle.terminal", "boolean", True),
    )
    if environment == "file_ops":
        return common + (
            SchemaField("files", "array<object>", True),
            SchemaField("files[].age_days", "integer", False, "day"),
            SchemaField("files[].path", "string", True),
            SchemaField("files[].protected", "boolean", True),
        )
    if environment == "calendar_ops":
        return common + (
            SchemaField("attendees", "array<string>", True),
            SchemaField("availability", "array<object>", True),
            SchemaField("availability[].end", "integer", True, "hour"),
            SchemaField("availability[].start", "integer", True, "hour"),
        )
    if environment == "risk_ops":
        return common + (
            SchemaField("exposure", "integer", True, "exposure_unit"),
            SchemaField("market_state", "object", True),
            SchemaField("market_state.snapshot_id", "string", True),
            SchemaField("market_state.volatility", "number", True, "ratio"),
        )
    raise KeyError(f"unknown schema environment: {environment!r}")


def _primary_paths(environment: str) -> tuple[str, str]:
    return {
        "file_ops": ("files", "items"),
        "calendar_ops": ("availability", "slots"),
        "risk_ops": ("market_state", "snapshot"),
    }[environment]


def _change(environment: str, family: str) -> SchemaChange:
    source, target = _primary_paths(environment)
    if family == "additive_field":
        return SchemaChange(family, None, "schema_capabilities", None, "object", compatibility="compatible")
    if family == "type_widening":
        path = {"file_ops": "files[].age_days", "calendar_ops": "availability[].start", "risk_ops": "exposure"}[
            environment
        ]
        return SchemaChange(family, path, path, "integer", "number", compatibility="compatible")
    if family == "alias_rename":
        value_type = "object" if environment == "risk_ops" else "array<object>"
        return SchemaChange(
            family,
            source,
            target,
            value_type,
            value_type,
            compatibility="requires_adaptation",
        )
    if family == "nested_field_move":
        return SchemaChange(
            family,
            "lifecycle.phase",
            "lifecycle.state.phase",
            "string",
            "string",
            compatibility="requires_adaptation",
        )
    if family == "unit_change":
        paths = {
            "file_ops": ("files[].age_days", "files[].age_hours", "day", "hour"),
            "calendar_ops": ("availability[].start", "availability[].start_minute", "hour", "minute"),
            "risk_ops": (
                "market_state.volatility",
                "market_state.volatility_basis_points",
                "ratio",
                "basis_point",
            ),
        }
        source_path, target_path, source_unit, target_unit = paths[environment]
        return SchemaChange(
            family,
            source_path,
            target_path,
            "number",
            "number",
            source_unit,
            target_unit,
            "requires_adaptation",
        )
    if family == "required_field_removal":
        return SchemaChange(family, "lifecycle", None, "object", None, compatibility="breaking")
    breaking_path = {
        "file_ops": "files[].protected",
        "calendar_ops": "attendees",
        "risk_ops": "market_state.snapshot_id",
    }[environment]
    target_type = "string" if environment == "file_ops" else "object"
    source_type = (
        "boolean" if environment == "file_ops" else "array<string>" if environment == "calendar_ops" else "string"
    )
    return SchemaChange(
        family,
        breaking_path,
        breaking_path,
        source_type,
        target_type,
        compatibility="breaking",
    )


def _target_fields(source: ToolSchema, changes: tuple[SchemaChange, ...]) -> tuple[SchemaField, ...]:
    fields = {field.path: field for field in source.fields}
    aliases: list[tuple[str, str]] = []

    def resolved(path: str | None) -> str | None:
        if path is None:
            return None
        for alias_source, alias_target in aliases:
            if path == alias_source or path.startswith(f"{alias_source}.") or path.startswith(f"{alias_source}[]"):
                return f"{alias_target}{path[len(alias_source) :]}"
        return path

    for change in changes:
        if change.family in {"alias_rename", "required_field_removal"} and change.source_path is not None:
            source_path = resolved(change.source_path)
            if source_path is None:
                continue
            matched = {
                path: field
                for path, field in fields.items()
                if path == source_path or path.startswith(f"{source_path}.") or path.startswith(f"{source_path}[]")
            }
            for path in matched:
                fields.pop(path)
            if change.target_path is not None:
                target_root = resolved(change.target_path) or change.target_path
                for path, field in matched.items():
                    target_path = f"{target_root}{path[len(source_path) :]}"
                    fields[target_path] = SchemaField(target_path, field.value_type, field.required, field.unit)
                aliases.append((change.source_path, target_root))
            continue
        source_path = resolved(change.source_path)
        target_path = resolved(change.target_path)
        previous = fields.pop(source_path, None) if source_path is not None else None
        if target_path is None:
            continue
        fields[target_path] = SchemaField(
            target_path,
            change.target_type or (previous.value_type if previous else "unknown"),
            previous.required if previous is not None else False,
            change.target_unit if change.target_unit is not None else previous.unit if previous is not None else None,
        )
    return tuple(fields.values())


class SchemaRegistry:
    def __init__(self) -> None:
        self._schemas = {
            (environment, "v1"): ToolSchema.create(environment, "v1", _baseline_fields(environment))
            for environment in ("file_ops", "calendar_ops", "risk_ops")
        }

    def get(self, environment: str, version: str = "v1") -> ToolSchema:
        try:
            return self._schemas[(environment, version)]
        except KeyError as exc:
            raise KeyError(f"unknown tool schema: {environment}@{version}") from exc

    def delta(
        self,
        environment: str,
        *,
        severity: float,
        rng: Random,
        families: tuple[str, ...] | None = None,
    ) -> SchemaDelta:
        if (
            not isinstance(severity, (int, float))
            or isinstance(severity, bool)
            or not math.isfinite(float(severity))
            or not 0.0 < float(severity) <= 1.0
        ):
            raise ValueError("schema drift severity must be finite and in (0, 1]")
        if families is None:
            count = min(len(SCHEMA_CHANGE_FAMILIES), max(1, math.ceil(float(severity) * 7)))
            selected = SCHEMA_CHANGE_FAMILIES[:count]
        else:
            unknown = set(families) - set(SCHEMA_CHANGE_FAMILIES)
            if unknown:
                raise ValueError(f"unknown schema change family: {sorted(unknown)[0]!r}")
            selected = families
        # Consume the supplied local RNG so repeated calls are still bound to
        # the declared fault stream even when a family has only one valid path.
        rng.randrange(2**31)
        changes = tuple(_change(environment, family) for family in selected)
        source = self.get(environment)
        draft_target = ToolSchema.create(environment, "pending", _target_fields(source, changes))
        version = f"v2_{stable_hash([asdict(change) for change in changes], prefix='delta').split('_', 1)[1]}"
        target = ToolSchema.create(environment, version, draft_target.fields)
        self._schemas[(environment, version)] = target
        return SchemaDelta.create(source, target, changes)


def _sequence_key(data: Mapping[str, Any], environment: str) -> str:
    source, target = _primary_paths(environment)
    return target if target in data else source


def apply_schema_delta(data: Mapping[str, Any], delta: SchemaDelta) -> dict[str, Any]:
    output = canonicalize(data)
    if not isinstance(output, dict):
        raise TypeError("tool data must normalize to a mapping")
    environment = delta.source_schema.environment
    for change in delta.changes:
        family = change.family
        if family == "additive_field":
            output["schema_capabilities"] = {"contract": SCHEMA_REGISTRY_CONTRACT, "delta": delta.delta_hash}
        elif family == "type_widening":
            if environment == "risk_ops" and isinstance(output.get("exposure"), int):
                output["exposure"] = float(output["exposure"])
            elif environment in {"file_ops", "calendar_ops"}:
                key = _sequence_key(output, environment)
                values = [dict(item) for item in output.get(key, [])]
                field = "age_days" if environment == "file_ops" else "start"
                for item in values:
                    if isinstance(item.get(field), int):
                        item[field] = float(item[field])
                output[key] = values
        elif family == "alias_rename":
            source, target = _primary_paths(environment)
            if source in output:
                output[target] = output.pop(source)
        elif family == "nested_field_move":
            lifecycle = dict(output.get("lifecycle", {}))
            if "phase" in lifecycle:
                state = dict(lifecycle.get("state", {}))
                state["phase"] = lifecycle.pop("phase")
                lifecycle["state"] = state
                output["lifecycle"] = lifecycle
        elif family == "unit_change":
            key = _sequence_key(output, environment)
            if environment == "file_ops":
                values = [dict(item) for item in output.get(key, [])]
                for item in values:
                    if "age_days" in item:
                        item["age_hours"] = float(item.pop("age_days")) * 24.0
                output[key] = values
            elif environment == "calendar_ops":
                values = [dict(item) for item in output.get(key, [])]
                for item in values:
                    if "start" in item:
                        item["start_minute"] = float(item.pop("start")) * 60.0
                output[key] = values
            else:
                state = dict(output.get(key, {}))
                if "volatility" in state:
                    state["volatility_basis_points"] = float(state.pop("volatility")) * 10_000.0
                output[key] = state
        elif family == "required_field_removal":
            output.pop("lifecycle", None)
        elif family == "breaking_type_change":
            key = _sequence_key(output, environment)
            if environment == "file_ops":
                values = [dict(item) for item in output.get(key, [])]
                for item in values:
                    if "protected" in item:
                        item["protected"] = "protected" if item["protected"] else "ordinary"
                output[key] = values
            elif environment == "calendar_ops":
                output["attendees"] = {"values": list(output.get("attendees", []))}
            else:
                state = dict(output.get(key, {}))
                if "snapshot_id" in state:
                    state["snapshot_id"] = {"value": state["snapshot_id"]}
                output[key] = state
    return output


def adapt_to_source_schema(data: Mapping[str, Any], delta: SchemaDelta) -> SchemaAdaptationResult:
    output = canonicalize(data)
    if not isinstance(output, dict):
        return SchemaAdaptationResult("failed", {}, (), ("tool_data_not_mapping",))
    if delta.compatibility_class == "breaking":
        families = tuple(change.family for change in delta.changes if change.compatibility == "breaking")
        return SchemaAdaptationResult("failed", output, (), tuple(f"unsupported:{family}" for family in families))
    environment = delta.source_schema.environment
    repairs: list[str] = []
    try:
        for change in reversed(delta.changes):
            family = change.family
            key = _sequence_key(output, environment)
            if family == "unit_change":
                if environment == "file_ops":
                    values = [dict(item) for item in output.get(key, [])]
                    for item in values:
                        if "age_hours" in item:
                            raw = item.pop("age_hours")
                            if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                                raise TypeError("age_hours_not_numeric")
                            item["age_days"] = int(float(raw) / 24.0)
                    output[key] = values
                elif environment == "calendar_ops":
                    values = [dict(item) for item in output.get(key, [])]
                    for item in values:
                        if "start_minute" in item:
                            raw = item.pop("start_minute")
                            if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                                raise TypeError("start_minute_not_numeric")
                            item["start"] = int(float(raw) / 60.0)
                    output[key] = values
                else:
                    state = dict(output.get(key, {}))
                    if "volatility_basis_points" in state:
                        raw = state.pop("volatility_basis_points")
                        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                            raise TypeError("volatility_basis_points_not_numeric")
                        state["volatility"] = float(raw) / 10_000.0
                    output[key] = state
                repairs.append(family)
            elif family == "nested_field_move":
                lifecycle = dict(output.get("lifecycle", {}))
                state = dict(lifecycle.get("state", {}))
                if "phase" in state:
                    lifecycle["phase"] = state.pop("phase")
                    if state:
                        lifecycle["state"] = state
                    else:
                        lifecycle.pop("state", None)
                    output["lifecycle"] = lifecycle
                repairs.append(family)
            elif family == "alias_rename":
                source, target = _primary_paths(environment)
                if target in output:
                    output[source] = output.pop(target)
                repairs.append(family)
            elif family == "type_widening":
                if environment == "risk_ops" and isinstance(output.get("exposure"), float):
                    if not output["exposure"].is_integer():
                        raise TypeError("exposure_not_integral")
                    output["exposure"] = int(output["exposure"])
                elif environment in {"file_ops", "calendar_ops"}:
                    key = _sequence_key(output, environment)
                    values = [dict(item) for item in output.get(key, [])]
                    field = "age_days" if environment == "file_ops" else "start"
                    for item in values:
                        if isinstance(item.get(field), float):
                            if not item[field].is_integer():
                                raise TypeError(f"{field}_not_integral")
                            item[field] = int(item[field])
                    output[key] = values
                repairs.append(family)
            elif family == "additive_field":
                output.pop("schema_capabilities", None)
        return SchemaAdaptationResult(
            "repaired" if repairs else "compatible",
            output,
            tuple(repairs),
            (),
        )
    except (TypeError, ValueError) as exc:
        return SchemaAdaptationResult("failed", output, tuple(repairs), (str(exc),))


def schema_delta_from_metadata(metadata: Mapping[str, Any]) -> SchemaDelta | None:
    info = metadata.get("schema_info")
    if not isinstance(info, Mapping) or info.get("contract") != SCHEMA_REGISTRY_CONTRACT:
        return None
    try:
        source_raw = info["source_schema"]
        target_raw = info["target_schema"]
        changes_raw = info["schema_delta"]["changes"]
        if (
            not isinstance(source_raw, Mapping)
            or not isinstance(target_raw, Mapping)
            or not isinstance(changes_raw, (list, tuple))
        ):
            return None
        source = ToolSchema(
            str(source_raw["contract"]),
            str(source_raw["environment"]),
            str(source_raw["version"]),
            tuple(SchemaField(**item) for item in source_raw["fields"]),
            str(source_raw["schema_hash"]),
        )
        target = ToolSchema(
            str(target_raw["contract"]),
            str(target_raw["environment"]),
            str(target_raw["version"]),
            tuple(SchemaField(**item) for item in target_raw["fields"]),
            str(target_raw["schema_hash"]),
        )
        changes = tuple(SchemaChange(**item) for item in changes_raw)
        delta = SchemaDelta.create(source, target, changes)
        expected_hash = info["schema_delta"].get("delta_hash")
        return delta if delta.delta_hash == expected_hash else None
    except (KeyError, TypeError, ValueError):
        return None


SCHEMA_REGISTRY = SchemaRegistry()


for _schema_dataclass in (
    SchemaField,
    ToolSchema,
    SchemaChange,
    SchemaDelta,
    SchemaAdaptationResult,
):
    register_dataclass(_schema_dataclass)
