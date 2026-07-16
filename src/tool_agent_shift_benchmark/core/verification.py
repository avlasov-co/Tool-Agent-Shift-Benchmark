"""Versioned integrity verification for self-contained run bundles."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping

from tool_agent_shift_benchmark.core.run_artifacts import (
    FINALIZATION_SCHEMA_VERSION,
    RUN_BUNDLE_LAYOUT_VERSION,
    RUN_MANIFEST_SCHEMA_VERSION,
    artifact_schema_version,
)
from tool_agent_shift_benchmark.core.scenarios import ScenarioSpec, manifest_filename
from tool_agent_shift_benchmark.core.serialization import canonical_dumps, canonical_loads, stable_hash

VERIFY_RUN_SCHEMA_VERSION = "verify-run-v1"
COMPLETE_VALID = "complete_valid"
INCOMPLETE_RESUMABLE = "incomplete_resumable"
INCOMPLETE_INVALID = "incomplete_invalid"
COMPLETE_CORRUPT = "complete_corrupt"
LEGACY_NEEDING_MIGRATION = "legacy_needing_migration"

_KNOWN_ARTIFACT_SCHEMAS = {
    "normalized-config-v1",
    "experiment-identity-v1",
    "plugin-descriptors-v2",
    "execution-plan-v1",
    "run-status-v1",
    "checkpoint-v2",
    "scenario-manifest-v3",
    "episode-trace-v1",
    "analysis-output-v1",
    "report-output-v1",
    "plot-output-v1",
    "log-output-v1",
    "canonical-jsonl-v1",
    "results-json-v2",
    "results-csv-v2",
    "opaque-artifact-v1",
}


def _read_json(path: Path, errors: list[str], label: str) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"missing required artifact: {label}")
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        value = canonical_loads(raw)
        if raw != canonical_dumps(value, pretty=True) + "\n":
            errors.append(f"non-canonical JSON serialization: {label}")
        if not isinstance(value, dict):
            errors.append(f"JSON object required: {label}")
            return None
        return value
    except Exception as exc:
        errors.append(f"invalid JSON artifact {label}: {type(exc).__name__}: {exc}")
        return None


def _read_jsonl(path: Path, errors: list[str], label: str) -> list[dict[str, Any]]:
    if not path.is_file():
        errors.append(f"missing required artifact: {label}")
        return []
    rows: list[dict[str, Any]] = []
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line:
                errors.append(f"blank JSONL row: {label}:{number}")
                continue
            value = canonical_loads(line)
            if line != canonical_dumps(value):
                errors.append(f"non-canonical JSONL row: {label}:{number}")
            if not isinstance(value, dict):
                errors.append(f"JSONL object required: {label}:{number}")
                continue
            rows.append(value)
    except Exception as exc:
        errors.append(f"invalid JSONL artifact {label}: {type(exc).__name__}: {exc}")
    return rows


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _episode_ids(rows: Iterable[Mapping[str, Any]], errors: list[str], label: str) -> set[str]:
    values: set[str] = set()
    for number, row in enumerate(rows, start=1):
        episode_id = row.get("episode_id")
        if not isinstance(episode_id, str) or not episode_id:
            errors.append(f"missing episode_id: {label}:{number}")
            continue
        if episode_id in values:
            errors.append(f"duplicate episode_id: {episode_id}")
        values.add(episode_id)
    return values


def _verify_plugin_descriptors(plan: Mapping[str, Any], plugins: Mapping[str, Any], errors: list[str]) -> None:
    descriptors = plugins.get("descriptors")
    if plugins.get("schema_version") != "plugin-descriptors-v2" or not isinstance(descriptors, list):
        errors.append("invalid plugin descriptor artifact")
        return
    by_key = {
        (item.get("kind"), item.get("name")): item
        for item in descriptors
        if isinstance(item, Mapping) and isinstance(item.get("kind"), str) and isinstance(item.get("name"), str)
    }
    for episode in plan.get("episodes", []):
        if not isinstance(episode, Mapping):
            continue
        identity = episode.get("identity")
        if not isinstance(identity, Mapping):
            continue
        components = [
            identity.get("environment"),
            identity.get("agent"),
            identity.get("monitor"),
            identity.get("evaluator"),
        ]
        shifts = identity.get("shift_chain")
        if isinstance(shifts, list):
            components.extend(shifts)
        for component in components:
            if not isinstance(component, Mapping):
                continue
            key = (component.get("kind"), component.get("name"))
            descriptor = by_key.get(key)
            if descriptor is None:
                errors.append(f"missing plugin descriptor: {key[0]}:{key[1]}")
            elif any(
                descriptor.get(field) != component.get(field)
                for field in (
                    "kind",
                    "name",
                    "version",
                    "contract_version",
                    "implementation_identifier",
                    "configuration_hash",
                    "trust_level",
                    "capabilities",
                    "isolation_mode",
                )
            ):
                errors.append(f"plugin descriptor mismatch: {key[0]}:{key[1]}")


def _verify_scenarios_and_traces(
    root: Path,
    plan: Mapping[str, Any],
    completed_ids: set[str],
    errors: list[str],
) -> None:
    for episode in plan.get("episodes", []):
        if not isinstance(episode, Mapping):
            continue
        reference = episode.get("scenario_manifest")
        if not isinstance(reference, Mapping):
            errors.append("planned episode has no scenario manifest reference")
            continue
        scenario_id = reference.get("scenario_id")
        content_hash = reference.get("content_hash")
        if not isinstance(scenario_id, str) or not isinstance(content_hash, str):
            errors.append("invalid scenario manifest reference")
            continue
        path = root / "scenarios" / manifest_filename(scenario_id, content_hash)
        payload = _read_json(path, errors, str(path.relative_to(root)))
        if payload is not None:
            try:
                scenario = ScenarioSpec.from_dict(payload)
                if scenario.content_hash != content_hash:
                    errors.append(f"scenario hash mismatch: {scenario_id}")
            except Exception as exc:
                errors.append(f"invalid scenario manifest {scenario_id}: {exc}")
    for episode_id in sorted(completed_ids):
        for trace_kind in ("policy", "evaluator"):
            path = root / "traces" / trace_kind / f"{episode_id}.json"
            payload = _read_json(path, errors, str(path.relative_to(root)))
            if payload is not None and payload.get("episode_id") != episode_id:
                errors.append(f"trace episode ID mismatch: {trace_kind}:{episode_id}")


def verify_run(bundle: str | Path) -> dict[str, Any]:
    """Classify and verify a bundle without mutating it."""

    root = Path(bundle)
    errors: list[str] = []
    if not root.is_dir():
        return {"schema_version": VERIFY_RUN_SCHEMA_VERSION, "status": INCOMPLETE_INVALID, "errors": ["bundle missing"]}
    manifest_path = root / "run_manifest.json"
    finalization_path = root / "finalization.json"
    if not manifest_path.exists():
        resumable = all(
            (root / relative).exists()
            for relative in (
                "config/normalized_config.json",
                "identity/experiment_identity.json",
                "plugins/descriptors.json",
                "plan/execution_plan.json",
                "status.json",
            )
        )
        legacy = (root / "results" / "config.json").exists() or (root / "results" / "episodes.jsonl").exists()
        return {
            "schema_version": VERIFY_RUN_SCHEMA_VERSION,
            "status": INCOMPLETE_RESUMABLE
            if resumable
            else (LEGACY_NEEDING_MIGRATION if legacy else INCOMPLETE_INVALID),
            "errors": [] if resumable or legacy else ["run manifest missing"],
        }
    manifest = _read_json(manifest_path, errors, "run_manifest.json")
    if manifest is None or manifest.get("artifact_schema_version") != RUN_MANIFEST_SCHEMA_VERSION:
        return {"schema_version": VERIFY_RUN_SCHEMA_VERSION, "status": LEGACY_NEEDING_MIGRATION, "errors": errors}
    if manifest.get("bundle_layout_version") != RUN_BUNDLE_LAYOUT_VERSION:
        errors.append("unsupported bundle layout version")
    artifact_schemas = manifest.get("artifact_schemas")
    checksums = manifest.get("checksums")
    if not isinstance(artifact_schemas, Mapping) or not isinstance(checksums, Mapping):
        errors.append("manifest lacks artifact schemas or checksums")
        artifact_schemas, checksums = {}, {}
    for relative, expected in checksums.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            errors.append("invalid checksum entry")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"missing checksummed artifact: {relative}")
        elif _checksum(path) != expected:
            errors.append(f"checksum mismatch: {relative}")
        declared = artifact_schemas.get(relative)
        if declared not in _KNOWN_ARTIFACT_SCHEMAS:
            errors.append(f"unknown artifact schema: {relative}:{declared}")
        elif declared != artifact_schema_version(relative):
            errors.append(f"artifact schema mismatch: {relative}")
    actual_files = {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.name not in {"run_manifest.json", "finalization.json"}
    }
    if actual_files != set(checksums):
        errors.append("manifest artifact inventory does not match bundle files")
    config = _read_json(root / "results" / "config.json", errors, "results/config.json")
    normalized = _read_json(root / "config" / "normalized_config.json", errors, "config/normalized_config.json")
    identity = _read_json(root / "identity" / "experiment_identity.json", errors, "identity/experiment_identity.json")
    plugins = _read_json(root / "plugins" / "descriptors.json", errors, "plugins/descriptors.json")
    plan = _read_json(root / "plan" / "execution_plan.json", errors, "plan/execution_plan.json")
    status = _read_json(root / "status.json", errors, "status.json")
    episodes = _read_jsonl(root / "results" / "episodes.jsonl", errors, "results/episodes.jsonl")
    failures = _read_jsonl(
        root / "results" / "orchestration_errors.jsonl", errors, "results/orchestration_errors.jsonl"
    )
    if config and identity:
        if config.get("run_id") != identity.get("run_id") or config.get("run_id") != manifest.get("run_id"):
            errors.append("cross-file run ID mismatch")
        if config.get("config_digest") != identity.get("config_digest"):
            errors.append("cross-file config digest mismatch")
        semantic = identity.get("semantic")
        if isinstance(semantic, Mapping) and stable_hash(dict(semantic), prefix="run") != identity.get("run_id"):
            errors.append("identity semantic run ID mismatch")
    if normalized is None:
        errors.append("normalized config unavailable")
    planned_ids = _episode_ids(plan.get("episodes", []) if plan else [], errors, "plan")
    completed_ids = _episode_ids(episodes, errors, "episodes")
    failed_ids = _episode_ids(
        [row["planned_episode"] for row in failures if isinstance(row.get("planned_episode"), Mapping)],
        errors,
        "failures",
    )
    if planned_ids and not completed_ids.issubset(planned_ids):
        errors.append("completed episode is absent from plan")
    if completed_ids & failed_ids:
        errors.append("episode appears as both completed and failed")
    if status and plan:
        planned = len(planned_ids)
        for field, expected in (
            ("planned_episodes", planned),
            ("completed_episodes", len(completed_ids)),
            ("failed_episodes", len(failed_ids)),
        ):
            if status.get(field) != expected:
                errors.append(f"status total mismatch: {field}")
        accounted = sum(
            int(status.get(name, 0) or 0)
            for name in (
                "completed_episodes",
                "failed_episodes",
                "skipped_episodes",
                "pending_episodes",
                "invalid_episodes",
            )
        )
        if accounted != planned:
            errors.append("status totals do not cover planned episodes")
    if plan and plugins:
        _verify_plugin_descriptors(plan, plugins, errors)
    if plan:
        _verify_scenarios_and_traces(root, plan, completed_ids, errors)
    finalized = _read_json(finalization_path, errors, "finalization.json") if finalization_path.exists() else None
    if finalized is None:
        return {
            "schema_version": VERIFY_RUN_SCHEMA_VERSION,
            "status": INCOMPLETE_INVALID if errors else INCOMPLETE_RESUMABLE,
            "errors": errors,
        }
    if finalized.get("schema_version") != FINALIZATION_SCHEMA_VERSION:
        errors.append("unknown finalization schema")
    if finalized.get("manifest_sha256") != _checksum(manifest_path):
        errors.append("stale finalization marker")
    if finalized.get("run_id") != manifest.get("run_id"):
        errors.append("finalization run ID mismatch")
    if finalized.get("artifact_count") != len(checksums):
        errors.append("finalization artifact count mismatch")
    return {
        "schema_version": VERIFY_RUN_SCHEMA_VERSION,
        "status": COMPLETE_CORRUPT if errors else COMPLETE_VALID,
        "errors": errors,
        "run_id": manifest.get("run_id"),
        "artifact_count": len(checksums),
    }


def legacy_migration_plan(bundle: str | Path) -> dict[str, Any]:
    """Return explicit, non-mutating guidance for a legacy bundle."""

    result = verify_run(bundle)
    return {
        "schema_version": "legacy-bundle-migration-plan-v1",
        "source": str(bundle),
        "verification_status": result["status"],
        "supported": result["status"] == LEGACY_NEEDING_MIGRATION,
        "steps": [
            "preserve the original bundle unchanged",
            "rerun the resolved configuration into a new run-bundle-v2 directory",
            "verify the new bundle before comparing or reporting it",
        ],
    }
