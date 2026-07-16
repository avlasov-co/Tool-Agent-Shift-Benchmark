"""Immutable, versioned scenario manifests and compatibility migration."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from tool_agent_shift_benchmark.core.serialization import (
    canonical_bytes,
    canonicalize,
    read_json,
    register_dataclass,
    stable_hash,
    write_json,
)

SCENARIO_MANIFEST_SCHEMA_VERSION = 3
SCENARIO_MANIFEST_CONTRACT = "scenario-manifest-v3"
SCENARIO_FAMILY_CONTRACT = "scenario-family-v1"
SCENARIO_SPLIT_CONTRACT = "scenario-split-v1"
SCENARIO_COVERAGE_CONTRACT = "scenario-coverage-v1"
SCENARIO_FAMILY_VERSION = "1.0.0"
SPLIT_NAMESPACE_SIZE = 1_000_000
STANDARD_SPLIT_ORDER = ("development", "validation", "challenge")
STANDARD_SPLIT_OFFSETS = {name: index * SPLIT_NAMESPACE_SIZE for index, name in enumerate(STANDARD_SPLIT_ORDER)}
APPLICABLE_SCENARIO_FAULTS = (
    "schema_drift",
    "stale_observation",
    "latency_spike",
    "missing_field",
    "conflicting_tool_output",
    "corrupted_memory",
    "constraint_shift",
)


class ScenarioManifestError(ValueError):
    """A manifest is malformed, unsupported, or has been modified."""


def standard_scenario_splits(count: int) -> tuple[dict[str, Any], ...]:
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError("standard scenario split count must be a positive integer")
    if count >= SPLIT_NAMESPACE_SIZE:
        raise ValueError("standard scenario split count exceeds its reserved namespace")
    return tuple(
        {
            "name": name,
            "indices": list(range(offset, offset + count)),
        }
        for name, offset in STANDARD_SPLIT_OFFSETS.items()
    )


def split_namespace_for_index(index: int) -> str:
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        raise ValueError("scenario index must be a non-negative integer")
    for name, offset in STANDARD_SPLIT_OFFSETS.items():
        if offset <= index < offset + SPLIT_NAMESPACE_SIZE:
            return name
    return "custom"


@dataclass(frozen=True)
class ScenarioFamilyDescriptor:
    contract: str
    name: str
    version: str
    task_type: str
    hazards: tuple[str, ...]
    protected_object_types: tuple[str, ...]
    constraint_dimensions: tuple[str, ...]
    temporal_behavior: tuple[str, ...]
    applicable_faults: tuple[str, ...]
    parameters: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.contract != SCENARIO_FAMILY_CONTRACT:
            raise ScenarioManifestError(f"unsupported scenario family contract: {self.contract!r}")
        for field_name, value in (
            ("name", self.name),
            ("version", self.version),
            ("task_type", self.task_type),
        ):
            if not isinstance(value, str) or not value:
                raise ScenarioManifestError(f"scenario family {field_name} must be non-empty")
        for field_name in (
            "hazards",
            "protected_object_types",
            "constraint_dimensions",
            "temporal_behavior",
            "applicable_faults",
        ):
            values = tuple(str(item) for item in getattr(self, field_name))
            if len(values) != len(set(values)):
                raise ScenarioManifestError(f"scenario family {field_name} must not contain duplicates")
            object.__setattr__(self, field_name, tuple(sorted(values)))
        object.__setattr__(self, "parameters", _freeze(_mapping(self.parameters, "family.parameters")))

    @classmethod
    def create(
        cls,
        *,
        name: str,
        task_type: str,
        hazards: Iterable[str],
        protected_object_types: Iterable[str],
        constraint_dimensions: Iterable[str],
        temporal_behavior: Iterable[str],
        parameters: Mapping[str, Any],
        applicable_faults: Iterable[str] = APPLICABLE_SCENARIO_FAULTS,
        version: str = SCENARIO_FAMILY_VERSION,
    ) -> "ScenarioFamilyDescriptor":
        return cls(
            SCENARIO_FAMILY_CONTRACT,
            name,
            version,
            task_type,
            tuple(hazards),
            tuple(protected_object_types),
            tuple(constraint_dimensions),
            tuple(temporal_behavior),
            tuple(applicable_faults),
            parameters,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ScenarioFamilyDescriptor":
        normalized = _mapping(value, "family")
        expected = {
            "contract",
            "name",
            "version",
            "task_type",
            "hazards",
            "protected_object_types",
            "constraint_dimensions",
            "temporal_behavior",
            "applicable_faults",
            "parameters",
        }
        if set(normalized) != expected:
            missing = sorted(expected - set(normalized))
            unknown = sorted(set(normalized) - expected)
            detail = f"missing {missing[0]}" if missing else f"unknown {unknown[0]}"
            raise ScenarioManifestError(f"invalid scenario family descriptor: {detail}")
        return cls(
            str(normalized["contract"]),
            str(normalized["name"]),
            str(normalized["version"]),
            str(normalized["task_type"]),
            tuple(str(item) for item in normalized["hazards"]),
            tuple(str(item) for item in normalized["protected_object_types"]),
            tuple(str(item) for item in normalized["constraint_dimensions"]),
            tuple(str(item) for item in normalized["temporal_behavior"]),
            tuple(str(item) for item in normalized["applicable_faults"]),
            normalized["parameters"],
        )

    def to_dict(self) -> dict[str, Any]:
        normalized = canonicalize(self)
        if not isinstance(normalized, dict):
            raise RuntimeError("scenario family did not normalize to a mapping")
        return normalized


@dataclass(frozen=True)
class ScenarioSplitDescriptor:
    contract: str
    name: str
    indices: tuple[int, ...]
    namespace: str

    def __post_init__(self) -> None:
        if self.contract != SCENARIO_SPLIT_CONTRACT or not self.name:
            raise ValueError("invalid scenario split descriptor")
        if not self.indices or any(index < 0 for index in self.indices):
            raise ValueError("scenario split indices must be non-empty and non-negative")
        if len(self.indices) != len(set(self.indices)):
            raise ValueError("scenario split indices must be unique")
        object.__setattr__(self, "indices", tuple(sorted(self.indices)))

    @classmethod
    def create(cls, name: str, indices: Iterable[int]) -> "ScenarioSplitDescriptor":
        values = tuple(int(index) for index in indices)
        namespaces = {split_namespace_for_index(index) for index in values}
        namespace = namespaces.pop() if len(namespaces) == 1 else "mixed"
        return cls(SCENARIO_SPLIT_CONTRACT, name, values, namespace)

    def to_dict(self) -> dict[str, Any]:
        normalized = canonicalize(self)
        if not isinstance(normalized, dict):
            raise RuntimeError("scenario split did not normalize to a mapping")
        return normalized


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in sorted(value.items())})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ScenarioManifestError(f"{field} must be a string-keyed mapping")
    normalized = canonicalize(value, path=f"$.{field}")
    if not isinstance(normalized, dict):
        raise ScenarioManifestError(f"{field} must normalize to a mapping")
    return normalized


def _sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class ScenarioSpec:
    """Authoritative scenario meaning, deeply immutable after construction."""

    schema_version: int
    contract: str
    generator_name: str
    generator_version: str
    environment: str
    scenario_id: str
    scenario_index: int
    scenario_seed: int
    seed_stream_algorithm: str
    split: str
    family: ScenarioFamilyDescriptor
    public_task_description: Mapping[str, Any]
    policy_visible_state: Mapping[str, Any]
    hidden_evaluator_state: Mapping[str, Any]
    constraints: Mapping[str, Any]
    transition_parameters: Mapping[str, Any]
    content_hash: str

    @classmethod
    def create(
        cls,
        *,
        generator_name: str,
        generator_version: str,
        environment: str,
        scenario_id: str,
        scenario_index: int,
        scenario_seed: int,
        seed_stream_algorithm: str,
        split: str,
        family: ScenarioFamilyDescriptor,
        public_task_description: Mapping[str, Any],
        policy_visible_state: Mapping[str, Any],
        hidden_evaluator_state: Mapping[str, Any],
        constraints: Mapping[str, Any],
        transition_parameters: Mapping[str, Any],
    ) -> "ScenarioSpec":
        if not isinstance(split, str) or not split:
            raise ScenarioManifestError("scenario split must be a non-empty string")
        if not isinstance(family, ScenarioFamilyDescriptor):
            raise ScenarioManifestError("scenario family must be a ScenarioFamilyDescriptor")
        payload = {
            "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
            "contract": SCENARIO_MANIFEST_CONTRACT,
            "generator_name": generator_name,
            "generator_version": generator_version,
            "environment": environment,
            "scenario_id": scenario_id,
            "scenario_index": int(scenario_index),
            "scenario_seed": int(scenario_seed),
            "seed_stream_algorithm": seed_stream_algorithm,
            "split": split,
            "family": family.to_dict(),
            "public_task_description": _mapping(public_task_description, "public_task_description"),
            "policy_visible_state": _mapping(policy_visible_state, "policy_visible_state"),
            "hidden_evaluator_state": _mapping(hidden_evaluator_state, "hidden_evaluator_state"),
            "constraints": _mapping(constraints, "constraints"),
            "transition_parameters": _mapping(transition_parameters, "transition_parameters"),
        }
        return cls(
            **{
                **payload,
                "public_task_description": _freeze(payload["public_task_description"]),
                "policy_visible_state": _freeze(payload["policy_visible_state"]),
                "hidden_evaluator_state": _freeze(payload["hidden_evaluator_state"]),
                "constraints": _freeze(payload["constraints"]),
                "transition_parameters": _freeze(payload["transition_parameters"]),
                "family": family,
                "content_hash": _sha256(payload),
            }
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ScenarioSpec":
        raw = dict(value)
        version = raw.get("schema_version")
        if version == 1:
            raw = migrate_scenario_manifest_v1(raw)
            version = raw["schema_version"]
        elif version == 2:
            raw = migrate_scenario_manifest_v2(raw)
            version = raw["schema_version"]
        if version != SCENARIO_MANIFEST_SCHEMA_VERSION:
            raise ScenarioManifestError(f"unsupported scenario manifest schema version: {version!r}")
        allowed = {
            "schema_version",
            "contract",
            "generator_name",
            "generator_version",
            "environment",
            "scenario_id",
            "scenario_index",
            "scenario_seed",
            "seed_stream_algorithm",
            "split",
            "family",
            "public_task_description",
            "policy_visible_state",
            "hidden_evaluator_state",
            "constraints",
            "transition_parameters",
            "content_hash",
        }
        unknown = sorted(set(raw) - allowed)
        missing = sorted(allowed - set(raw))
        if unknown:
            raise ScenarioManifestError(f"unknown scenario manifest field: {unknown[0]}")
        if missing:
            raise ScenarioManifestError(f"missing scenario manifest field: {missing[0]}")
        if raw["contract"] != SCENARIO_MANIFEST_CONTRACT:
            raise ScenarioManifestError(f"unsupported scenario manifest contract: {raw['contract']!r}")
        created = cls.create(
            generator_name=str(raw["generator_name"]),
            generator_version=str(raw["generator_version"]),
            environment=str(raw["environment"]),
            scenario_id=str(raw["scenario_id"]),
            scenario_index=int(raw["scenario_index"]),
            scenario_seed=int(raw["scenario_seed"]),
            seed_stream_algorithm=str(raw["seed_stream_algorithm"]),
            split=str(raw["split"]),
            family=ScenarioFamilyDescriptor.from_dict(raw["family"]),
            public_task_description=_mapping(raw["public_task_description"], "public_task_description"),
            policy_visible_state=_mapping(raw["policy_visible_state"], "policy_visible_state"),
            hidden_evaluator_state=_mapping(raw["hidden_evaluator_state"], "hidden_evaluator_state"),
            constraints=_mapping(raw["constraints"], "constraints"),
            transition_parameters=_mapping(raw["transition_parameters"], "transition_parameters"),
        )
        if not isinstance(raw["content_hash"], str) or raw["content_hash"] != created.content_hash:
            raise ScenarioManifestError(
                f"scenario manifest hash mismatch: expected {created.content_hash}, got {raw['content_hash']!r}"
            )
        return created

    def to_dict(self) -> dict[str, Any]:
        normalized = canonicalize(self)
        if not isinstance(normalized, dict):
            raise RuntimeError("scenario manifest did not normalize to a mapping")
        return normalized

    def public_reference(self) -> dict[str, Any]:
        """Return the planner-safe reference without hidden scenario fields."""

        return {
            "schema_version": self.schema_version,
            "contract": self.contract,
            "environment": self.environment,
            "scenario_id": self.scenario_id,
            "scenario_index": self.scenario_index,
            "scenario_seed": self.scenario_seed,
            "generator_name": self.generator_name,
            "generator_version": self.generator_version,
            "split_contract": SCENARIO_SPLIT_CONTRACT,
            "split": self.split,
            "family": {
                "contract": self.family.contract,
                "name": self.family.name,
                "version": self.family.version,
                "task_type": self.family.task_type,
            },
            "content_hash": self.content_hash,
        }

    def with_split(self, split: str) -> "ScenarioSpec":
        if split == self.split:
            return self
        return ScenarioSpec.create(
            generator_name=self.generator_name,
            generator_version=self.generator_version,
            environment=self.environment,
            scenario_id=self.scenario_id,
            scenario_index=self.scenario_index,
            scenario_seed=self.scenario_seed,
            seed_stream_algorithm=self.seed_stream_algorithm,
            split=split,
            family=self.family,
            public_task_description=self.public_task_description,
            policy_visible_state=self.policy_visible_state,
            hidden_evaluator_state=self.hidden_evaluator_state,
            constraints=self.constraints,
            transition_parameters=self.transition_parameters,
        )


def migrate_scenario_manifest_v1(value: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate the explicit reconstructible legacy shape to schema v3.

    Historical episodes without these fields cannot be safely reconstructed and
    are intentionally not guessed into a manifest.
    """

    raw = dict(value)
    required = {
        "schema_version",
        "generator",
        "environment",
        "scenario_id",
        "scenario_index",
        "scenario_seed",
        "task",
        "visible_state",
        "hidden_state",
        "constraints",
        "transition_parameters",
    }
    if set(raw) != required:
        missing = sorted(required - set(raw))
        unknown = sorted(set(raw) - required)
        detail = f"missing {missing[0]}" if missing else f"unknown {unknown[0]}"
        raise ScenarioManifestError(f"legacy scenario manifest is not reconstructible: {detail}")
    generator = _mapping(raw["generator"], "generator")
    environment = str(raw["environment"])
    task = _mapping(raw["task"], "task")
    constraints = _mapping(raw["constraints"], "constraints")
    spec = ScenarioSpec.create(
        generator_name=str(generator["name"]),
        generator_version=str(generator["version"]),
        environment=environment,
        scenario_id=str(raw["scenario_id"]),
        scenario_index=int(raw["scenario_index"]),
        scenario_seed=int(raw["scenario_seed"]),
        seed_stream_algorithm="legacy-explicit-seed-v1",
        split="legacy",
        family=_legacy_family(environment, task, constraints),
        public_task_description=task,
        policy_visible_state=_mapping(raw["visible_state"], "visible_state"),
        hidden_evaluator_state=_mapping(raw["hidden_state"], "hidden_state"),
        constraints=constraints,
        transition_parameters=_mapping(raw["transition_parameters"], "transition_parameters"),
    )
    return spec.to_dict()


def migrate_scenario_manifest_v2(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and migrate the complete hashed v2 manifest to schema v3."""

    raw = dict(value)
    expected = {
        "schema_version",
        "contract",
        "generator_name",
        "generator_version",
        "environment",
        "scenario_id",
        "scenario_index",
        "scenario_seed",
        "seed_stream_algorithm",
        "public_task_description",
        "policy_visible_state",
        "hidden_evaluator_state",
        "constraints",
        "transition_parameters",
        "content_hash",
    }
    if set(raw) != expected or raw.get("contract") != "scenario-manifest-v2":
        missing = sorted(expected - set(raw))
        unknown = sorted(set(raw) - expected)
        detail = f"missing {missing[0]}" if missing else f"unknown {unknown[0]}" if unknown else "invalid contract"
        raise ScenarioManifestError(f"legacy scenario manifest v2 is not reconstructible: {detail}")
    old_payload = {key: raw[key] for key in expected if key != "content_hash"}
    if not isinstance(raw["content_hash"], str) or raw["content_hash"] != _sha256(old_payload):
        raise ScenarioManifestError("legacy scenario manifest v2 hash mismatch")
    environment = str(raw["environment"])
    task = _mapping(raw["public_task_description"], "public_task_description")
    constraints = _mapping(raw["constraints"], "constraints")
    return ScenarioSpec.create(
        generator_name=str(raw["generator_name"]),
        generator_version=str(raw["generator_version"]),
        environment=environment,
        scenario_id=str(raw["scenario_id"]),
        scenario_index=int(raw["scenario_index"]),
        scenario_seed=int(raw["scenario_seed"]),
        seed_stream_algorithm=str(raw["seed_stream_algorithm"]),
        split="legacy",
        family=_legacy_family(environment, task, constraints),
        public_task_description=task,
        policy_visible_state=_mapping(raw["policy_visible_state"], "policy_visible_state"),
        hidden_evaluator_state=_mapping(raw["hidden_evaluator_state"], "hidden_evaluator_state"),
        constraints=constraints,
        transition_parameters=_mapping(raw["transition_parameters"], "transition_parameters"),
    ).to_dict()


def _legacy_family(
    environment: str,
    task: Mapping[str, Any],
    constraints: Mapping[str, Any],
) -> ScenarioFamilyDescriptor:
    task_type = str(task.get("task", task.get("objective", "legacy_task")))
    return ScenarioFamilyDescriptor.create(
        name=f"{environment}_legacy_template",
        version="legacy",
        task_type=task_type,
        hazards=("legacy_unclassified",),
        protected_object_types=("legacy_unclassified",),
        constraint_dimensions=tuple(str(key) for key in constraints),
        temporal_behavior=("legacy_unclassified",),
        applicable_faults=(),
        parameters={"migration": "legacy_manifest"},
    )


def manifest_filename(scenario_id: str, content_hash: str | None = None) -> str:
    if not scenario_id or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in scenario_id
    ):
        raise ScenarioManifestError(f"unsafe scenario identifier for manifest path: {scenario_id!r}")
    suffix = f".{content_hash}" if content_hash else ""
    return f"{scenario_id}{suffix}.json"


def write_scenario_manifest(directory: str | Path, spec: ScenarioSpec) -> Path:
    target = Path(directory) / manifest_filename(spec.scenario_id, spec.content_hash)
    if target.exists():
        existing = ScenarioSpec.from_dict(read_json(target))
        if existing.content_hash != spec.content_hash:
            raise ScenarioManifestError(f"refusing to overwrite scenario {spec.scenario_id!r} with different content")
        return target
    write_json(target, spec.to_dict())
    return target


def read_scenario_manifest(
    directory: str | Path,
    scenario_id: str,
    *,
    scenario_seed: int | None = None,
) -> ScenarioSpec:
    root = Path(directory)
    legacy_path = root / manifest_filename(scenario_id)
    candidates = ([legacy_path] if legacy_path.is_file() else []) + sorted(root.glob(f"{scenario_id}.*.json"))
    matched: list[ScenarioSpec] = []
    for path in candidates:
        value = read_json(path)
        if not isinstance(value, dict):
            raise ScenarioManifestError(f"scenario manifest root must be a mapping: {path}")
        scenario = ScenarioSpec.from_dict(value)
        if scenario_seed is None or scenario.scenario_seed == scenario_seed:
            matched.append(scenario)
    if not matched:
        raise ScenarioManifestError(
            f"scenario manifest not found for {scenario_id!r} and seed {scenario_seed!r} in {root}"
        )
    if len(matched) != 1:
        raise ScenarioManifestError(
            f"ambiguous scenario manifests for {scenario_id!r} and seed {scenario_seed!r} in {root}"
        )
    return matched[0]


def scenario_coverage_summary(specs: Iterable[ScenarioSpec]) -> dict[str, Any]:
    unique = {spec.content_hash: spec for spec in specs}
    dimensions: dict[str, Counter[str]] = {
        "environment": Counter(),
        "split": Counter(),
        "family": Counter(),
        "task_type": Counter(),
        "hazard": Counter(),
        "protected_object_type": Counter(),
        "constraint_dimension": Counter(),
        "temporal_behavior": Counter(),
        "applicable_fault": Counter(),
    }
    for spec in unique.values():
        family = spec.family
        dimensions["environment"][spec.environment] += 1
        dimensions["split"][spec.split] += 1
        dimensions["family"][family.name] += 1
        dimensions["task_type"][family.task_type] += 1
        for dimension, values in (
            ("hazard", family.hazards or ("none",)),
            ("protected_object_type", family.protected_object_types or ("none",)),
            ("constraint_dimension", family.constraint_dimensions or ("none",)),
            ("temporal_behavior", family.temporal_behavior or ("none",)),
            ("applicable_fault", family.applicable_faults or ("none",)),
        ):
            for value in values:
                dimensions[dimension][value] += 1
    payload = {
        "contract": SCENARIO_COVERAGE_CONTRACT,
        "scenario_manifest_contract": SCENARIO_MANIFEST_CONTRACT,
        "scenario_family_contract": SCENARIO_FAMILY_CONTRACT,
        "scenario_split_contract": SCENARIO_SPLIT_CONTRACT,
        "scenario_count": len(unique),
        "dimensions": {name: {key: counter[key] for key in sorted(counter)} for name, counter in dimensions.items()},
    }
    return {**payload, "coverage_hash": stable_hash(payload, prefix="coverage")}


def scenario_coverage_rows(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dimensions = summary.get("dimensions", {})
    if not isinstance(dimensions, Mapping):
        raise ValueError("scenario coverage dimensions must be a mapping")
    for dimension in sorted(dimensions):
        counts = dimensions[dimension]
        if not isinstance(counts, Mapping):
            raise ValueError(f"scenario coverage dimension {dimension!r} must be a mapping")
        for value in sorted(counts):
            rows.append(
                {
                    "coverage_contract": summary.get("contract", SCENARIO_COVERAGE_CONTRACT),
                    "coverage_hash": summary.get("coverage_hash", ""),
                    "scenario_count": summary.get("scenario_count", 0),
                    "dimension": dimension,
                    "value": value,
                    "count": counts[value],
                }
            )
    return rows


register_dataclass(ScenarioFamilyDescriptor)
register_dataclass(ScenarioSplitDescriptor)
register_dataclass(ScenarioSpec)
