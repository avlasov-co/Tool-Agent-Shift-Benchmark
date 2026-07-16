"""Versioned, compatibility-checked checkpoints for deterministic recovery."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tool_agent_shift_benchmark.core.serialization import canonicalize

CHECKPOINT_SCHEMA_VERSION = "checkpoint-v2"

# These describe the records a resumed execution may rely on.  A checkpoint
# from a different artifact contract is never silently interpreted as current.
CHECKPOINT_ARTIFACT_SCHEMAS = {
    "checkpoint": CHECKPOINT_SCHEMA_VERSION,
    "normalized_config": "normalized-config-v1",
    "identity": "experiment-identity-v1",
    "plugins": "plugin-descriptors-v2",
    "execution_plan": "execution-plan-v1",
    "status": "run-status-v1",
    "episodes": "canonical-jsonl-v1",
    "traces": "episode-trace-v1",
}

_OPERATIONAL_CONFIG_KEYS = frozenset(
    {
        "workers",
        "logging",
        "output_path",
        "working_directory",
        "progress_display",
        "execution_batch_size",
        "episode_ids",
        "scenario_indices",
        "selection_offset",
        "selection_limit",
        "partition_index",
        "partition_count",
        "replay_episode_ids",
        "resume_episode_ids",
    }
)


def normalized_scientific_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Remove only documented operational settings from a normalized config."""

    value = canonicalize(
        {key: item for key, item in config.items() if not key.startswith("_") and key not in _OPERATIONAL_CONFIG_KEYS}
    )
    if not isinstance(value, dict):  # pragma: no cover - canonicalize preserves mappings
        raise RuntimeError("normalized scientific configuration is not an object")
    return value


def checkpoint_payload(
    *,
    run_id: str,
    identity: Mapping[str, Any],
    normalized_config: Mapping[str, Any],
    plugin_descriptors: Sequence[Mapping[str, Any]],
    scenario_manifest_hashes: Sequence[Mapping[str, str]],
    planned_episode_ids: set[str],
    completed_episode_ids: set[str],
    failed_episode_ids: set[str],
    errors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one canonical checkpoint state from already durable progress."""

    pending_episode_ids = planned_episode_ids - completed_episode_ids - failed_episode_ids
    status = {
        "planned_episodes": len(planned_episode_ids),
        "started_episodes": len(completed_episode_ids | failed_episode_ids),
        "completed_episodes": len(completed_episode_ids),
        "failed_episodes": len(failed_episode_ids),
        "skipped_episodes": 0,
        "pending_episodes": len(pending_episode_ids),
        "invalid_episodes": 0,
    }
    payload = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "run_id": run_id,
        "identity": dict(identity),
        "config_digest": identity.get("config_digest"),
        "normalized_config": normalized_scientific_config(normalized_config),
        "operational_settings": dict(identity.get("operational", {})),
        "plugin_descriptors": [dict(descriptor) for descriptor in plugin_descriptors],
        "scenario_manifest_hashes": [dict(item) for item in scenario_manifest_hashes],
        "artifact_schema_versions": dict(CHECKPOINT_ARTIFACT_SCHEMAS),
        "completed_episode_ids": sorted(completed_episode_ids),
        "failed_episode_ids": sorted(failed_episode_ids),
        "pending_episode_ids": sorted(pending_episode_ids),
        "status": status,
        "errors": [dict(error) for error in errors],
        # Compatibility fields retained for existing readers.
        "episode_record_version": identity.get("semantic", {}).get("episode_record_version", "unknown"),
        "action_record_contract": identity.get("semantic", {}).get("action_record_contract", "unknown"),
        "counterfactual_evaluation_contract": identity.get("semantic", {}).get(
            "counterfactual_evaluation_contract", "unknown"
        ),
        "scenario_manifest_contract": identity.get("semantic", {}).get("scenario_manifest_contract", "unknown"),
        "scenario_family_contract": identity.get("semantic", {}).get("scenario_family_contract", "unknown"),
        "scenario_split_contract": identity.get("semantic", {}).get("scenario_split_contract", "unknown"),
    }
    completed_pairs = {
        str(item.get("scenario_pair_id"))
        for item in scenario_manifest_hashes
        if isinstance(item.get("scenario_pair_id"), str) and item.get("scenario_pair_id")
    }
    payload["completed_scenario_pair_ids"] = sorted(completed_pairs)
    normalized = canonicalize(payload)
    if not isinstance(normalized, dict):  # pragma: no cover - canonicalize preserves mappings
        raise RuntimeError("checkpoint payload is not an object")
    return normalized


def checkpoint_compatibility_issues(
    saved: Mapping[str, Any],
    *,
    run_id: str,
    identity: Mapping[str, Any],
    normalized_config: Mapping[str, Any],
    plugin_descriptors: Sequence[Mapping[str, Any]],
    scenario_manifest_hashes: Sequence[Mapping[str, str]],
) -> list[tuple[str, Any, Any]]:
    """Return exact incompatible checkpoint fields without changing state."""

    expected = {
        "checkpoint.schema_version": CHECKPOINT_SCHEMA_VERSION,
        "checkpoint.run_id": run_id,
        "checkpoint.config_digest": identity.get("config_digest"),
        "checkpoint.identity.semantic": canonicalize(identity.get("semantic")),
        "checkpoint.normalized_config": normalized_scientific_config(normalized_config),
        "checkpoint.plugin_descriptors": canonicalize([dict(item) for item in plugin_descriptors]),
        "checkpoint.scenario_manifest_hashes": canonicalize([dict(item) for item in scenario_manifest_hashes]),
        "checkpoint.artifact_schema_versions": canonicalize(CHECKPOINT_ARTIFACT_SCHEMAS),
    }
    actual = {
        "checkpoint.schema_version": saved.get("schema_version"),
        "checkpoint.run_id": saved.get("run_id"),
        "checkpoint.config_digest": saved.get("config_digest"),
        "checkpoint.identity.semantic": (
            saved.get("identity", {}).get("semantic") if isinstance(saved.get("identity"), Mapping) else None
        ),
        "checkpoint.normalized_config": saved.get("normalized_config"),
        "checkpoint.plugin_descriptors": saved.get("plugin_descriptors"),
        "checkpoint.scenario_manifest_hashes": saved.get("scenario_manifest_hashes"),
        "checkpoint.artifact_schema_versions": saved.get("artifact_schema_versions"),
    }
    # Run ID remains first for compatibility with callers that already treat it
    # as the authoritative identity boundary.
    order = (
        "checkpoint.run_id",
        "checkpoint.schema_version",
        "checkpoint.config_digest",
        "checkpoint.identity.semantic",
        "checkpoint.normalized_config",
        "checkpoint.plugin_descriptors",
        "checkpoint.scenario_manifest_hashes",
        "checkpoint.artifact_schema_versions",
    )
    return [(field, expected[field], actual[field]) for field in order if expected[field] != actual[field]]
