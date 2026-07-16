from __future__ import annotations

import hashlib
from pathlib import Path

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.run_artifacts import FINALIZATION_SCHEMA_VERSION, artifact_schema_version
from tool_agent_shift_benchmark.core.scenarios import manifest_filename
from tool_agent_shift_benchmark.core.serialization import canonical_loads, read_json, write_json, write_jsonl
from tool_agent_shift_benchmark.core.verification import (
    COMPLETE_CORRUPT,
    COMPLETE_VALID,
    INCOMPLETE_RESUMABLE,
    verify_run,
)
from tool_agent_shift_benchmark.run_eval import run_eval


def _write_config(path: Path) -> None:
    path.write_text(
        """schema_version: 2
environments: [file_ops]
agents: [naive]
faults: [normal]
fault_severities: [1.0]
episodes_per_combo: 1
""",
        encoding="utf-8",
    )


def _complete_bundle(tmp_path: Path) -> Path:
    config = tmp_path / "config.yaml"
    _write_config(config)
    store = ArtifactStore(tmp_path / "bundle")
    run_eval(str(config), seed=43, artifact_store=store, checkpoint_path=str(store.run_dir / "checkpoint.json"))
    store.finalize(command=["tasb", "run"])
    assert verify_run(store.run_dir)["status"] == COMPLETE_VALID
    return store.run_dir


def _refresh_integrity_markers(root: Path) -> None:
    manifest_path = root / "run_manifest.json"
    manifest = read_json(manifest_path)
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.name not in {"run_manifest.json", "finalization.json"}
    )
    artifacts = [str(path.relative_to(root)) for path in files]
    manifest["artifacts"] = artifacts
    manifest["checksums"] = {
        relative: hashlib.sha256((root / relative).read_bytes()).hexdigest() for relative in artifacts
    }
    manifest["artifact_schemas"] = {
        relative: manifest.get("artifact_schemas", {}).get(relative, artifact_schema_version(relative))
        for relative in artifacts
    }
    write_json(manifest_path, manifest)
    write_json(
        root / "finalization.json",
        {
            "schema_version": FINALIZATION_SCHEMA_VERSION,
            "run_id": manifest["run_id"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "artifact_count": len(artifacts),
        },
    )


def test_verify_run_classifies_an_unfinalized_bundle_as_resumable(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    _write_config(config)
    store = ArtifactStore(tmp_path / "bundle")
    run_eval(str(config), seed=43, artifact_store=store)

    assert verify_run(store.run_dir)["status"] == INCOMPLETE_RESUMABLE


def test_verify_run_detects_corruption_even_when_the_manifest_is_recomputed(tmp_path: Path) -> None:
    root = _complete_bundle(tmp_path)

    episodes_path = root / "results" / "episodes.jsonl"
    row = canonical_loads(episodes_path.read_text(encoding="utf-8").splitlines()[0])
    write_jsonl(episodes_path, [row, row])
    _refresh_integrity_markers(root)
    duplicate = verify_run(root)
    assert duplicate["status"] == COMPLETE_CORRUPT
    assert any("duplicate episode_id" in error for error in duplicate["errors"])


def test_verify_run_detects_missing_referenced_scenario(tmp_path: Path) -> None:
    root = _complete_bundle(tmp_path)
    plan = read_json(root / "plan" / "execution_plan.json")
    reference = plan["episodes"][0]["scenario_manifest"]
    (root / "scenarios" / manifest_filename(reference["scenario_id"], reference["content_hash"])).unlink()
    _refresh_integrity_markers(root)

    result = verify_run(root)
    assert result["status"] == COMPLETE_CORRUPT
    assert any("missing required artifact: scenarios/" in error for error in result["errors"])


def test_verify_run_detects_cross_file_identity_mismatch(tmp_path: Path) -> None:
    root = _complete_bundle(tmp_path)
    config = read_json(root / "results" / "config.json")
    config["run_id"] = "run_corrupted"
    write_json(root / "results" / "config.json", config)
    _refresh_integrity_markers(root)

    result = verify_run(root)
    assert result["status"] == COMPLETE_CORRUPT
    assert "cross-file run ID mismatch" in result["errors"]


def test_verify_run_detects_truncated_jsonl_and_stale_markers(tmp_path: Path) -> None:
    root = _complete_bundle(tmp_path)
    episodes_path = root / "results" / "episodes.jsonl"
    episodes_path.write_text('{"episode_id":', encoding="utf-8")
    _refresh_integrity_markers(root)
    result = verify_run(root)
    assert result["status"] == COMPLETE_CORRUPT
    assert any("invalid JSONL artifact results/episodes.jsonl" in error for error in result["errors"])

    manifest = read_json(root / "run_manifest.json")
    manifest["metadata"]["post_finalization_change"] = True
    write_json(root / "run_manifest.json", manifest)
    stale = verify_run(root)
    assert stale["status"] == COMPLETE_CORRUPT
    assert "stale finalization marker" in stale["errors"]


def test_verify_run_rejects_unknown_artifact_schema_and_checksum_mismatch(tmp_path: Path) -> None:
    root = _complete_bundle(tmp_path)
    manifest_path = root / "run_manifest.json"
    manifest = read_json(manifest_path)
    manifest["artifact_schemas"]["results/config.json"] = "unrecognized-schema-v9"
    write_json(manifest_path, manifest)
    _refresh_integrity_markers(root)
    unknown = verify_run(root)
    assert unknown["status"] == COMPLETE_CORRUPT
    assert any("unknown artifact schema" in error for error in unknown["errors"])

    manifest = read_json(manifest_path)
    manifest["checksums"]["results/summary.csv"] = "0" * 64
    write_json(manifest_path, manifest)
    write_json(
        root / "finalization.json",
        {
            "schema_version": FINALIZATION_SCHEMA_VERSION,
            "run_id": manifest["run_id"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "artifact_count": len(manifest["checksums"]),
        },
    )
    checksum = verify_run(root)
    assert checksum["status"] == COMPLETE_CORRUPT
    assert "checksum mismatch: results/summary.csv" in checksum["errors"]
