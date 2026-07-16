"""Immutable, versioned scenario manifests and compatibility migration."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from tool_agent_shift_benchmark.core.serialization import (
    canonical_bytes,
    canonicalize,
    read_json,
    register_dataclass,
    write_json,
)

SCENARIO_MANIFEST_SCHEMA_VERSION = 2
SCENARIO_MANIFEST_CONTRACT = "scenario-manifest-v2"


class ScenarioManifestError(ValueError):
    """A manifest is malformed, unsupported, or has been modified."""


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
        public_task_description: Mapping[str, Any],
        policy_visible_state: Mapping[str, Any],
        hidden_evaluator_state: Mapping[str, Any],
        constraints: Mapping[str, Any],
        transition_parameters: Mapping[str, Any],
    ) -> "ScenarioSpec":
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
            "content_hash": self.content_hash,
        }


def migrate_scenario_manifest_v1(value: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate the explicit reconstructible legacy shape to schema v2.

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
    spec = ScenarioSpec.create(
        generator_name=str(generator["name"]),
        generator_version=str(generator["version"]),
        environment=str(raw["environment"]),
        scenario_id=str(raw["scenario_id"]),
        scenario_index=int(raw["scenario_index"]),
        scenario_seed=int(raw["scenario_seed"]),
        seed_stream_algorithm="legacy-explicit-seed-v1",
        public_task_description=_mapping(raw["task"], "task"),
        policy_visible_state=_mapping(raw["visible_state"], "visible_state"),
        hidden_evaluator_state=_mapping(raw["hidden_state"], "hidden_state"),
        constraints=_mapping(raw["constraints"], "constraints"),
        transition_parameters=_mapping(raw["transition_parameters"], "transition_parameters"),
    )
    return spec.to_dict()


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


register_dataclass(ScenarioSpec)
