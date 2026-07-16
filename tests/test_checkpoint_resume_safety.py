from __future__ import annotations

from pathlib import Path

import pytest

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.contracts import IdentityMismatchError
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.execution import ExecutionRequest, normalize_execution_request
from tool_agent_shift_benchmark.core.orchestration import EpisodeRunner, ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.serialization import canonical_loads, read_json
from tool_agent_shift_benchmark.core.verification import COMPLETE_VALID, INCOMPLETE_RESUMABLE, verify_run
from tool_agent_shift_benchmark.run_eval import run_eval


class InjectedCrash(RuntimeError):
    pass


def _write_config(path: Path, *, workers: int = 1) -> None:
    path.write_text(
        f"""schema_version: 2
environments: [file_ops]
agents: [naive]
faults: [normal]
fault_severities: [1.0]
episodes_per_combo: 3
episode_steps: 1
workers: {workers}
execution_batch_size: 1
""",
        encoding="utf-8",
    )


def _episodes(root: Path) -> list[Episode]:
    path = root / "results" / "episodes.jsonl"
    if not path.exists():
        return []
    return [Episode.from_dict(canonical_loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _resume(config: Path, store: ArtifactStore) -> list[Episode]:
    episodes = run_eval(
        str(config),
        seed=73,
        artifact_store=store,
        existing_episodes=_episodes(store.run_dir),
        checkpoint_path=str(store.run_dir / "checkpoint.json"),
    )
    store.finalize(command=["tasb", "run", "--resume"])
    return episodes


def _data_files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.name not in {"run_manifest.json", "finalization.json"}
    }


@pytest.mark.parametrize(
    "phase",
    [
        "before_execution",
        "after_execution_before_write",
        "during_trace_write",
        "after_status_write",
        "before_finalization",
    ],
)
def test_failure_injection_recovers_without_duplicate_rows_and_matches_uninterrupted_output(
    tmp_path: Path, phase: str
) -> None:
    config = tmp_path / "config.yaml"
    _write_config(config)

    uninterrupted = ArtifactStore(tmp_path / "uninterrupted")
    run_eval(
        str(config),
        seed=73,
        artifact_store=uninterrupted,
        checkpoint_path=str(uninterrupted.run_dir / "checkpoint.json"),
    )
    uninterrupted.finalize(command=["tasb", "run"])

    interrupted = ArtifactStore(tmp_path / "interrupted")

    def inject(current_phase: str) -> None:
        if current_phase == phase:
            raise InjectedCrash(phase)

    with pytest.raises(InjectedCrash, match=phase):
        run_eval(
            str(config),
            seed=73,
            artifact_store=interrupted,
            checkpoint_path=str(interrupted.run_dir / "checkpoint.json"),
            failure_injector=inject,
        )

    assert verify_run(interrupted.run_dir)["status"] == INCOMPLETE_RESUMABLE
    resumed = _resume(config, interrupted)
    assert verify_run(interrupted.run_dir)["status"] == COMPLETE_VALID
    assert len(resumed) == 3
    assert len({episode.episode_id for episode in resumed}) == 3
    assert _data_files(interrupted.run_dir) == _data_files(uninterrupted.run_dir)


def _direct_config(*, workers: int = 1, policy_hash: str = "a" * 64) -> dict[str, object]:
    return {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["normal"],
        "fault_severities": [1.0],
        "episodes_per_combo": 2,
        "episode_steps": 1,
        "workers": workers,
        "execution_batch_size": 1,
        "policy_resources": {"fixture": policy_hash},
    }


def test_checkpoint_records_required_compatibility_state_and_allows_worker_only_change(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    first = ExperimentSpec.from_config(_direct_config(workers=1), seed=79)
    RunCoordinator(first).run(checkpoint_path=checkpoint)
    saved = read_json(checkpoint)

    assert saved["schema_version"] == "checkpoint-v2"
    assert set(saved) >= {
        "identity",
        "normalized_config",
        "plugin_descriptors",
        "scenario_manifest_hashes",
        "artifact_schema_versions",
        "completed_episode_ids",
        "failed_episode_ids",
        "pending_episode_ids",
        "status",
    }
    assert saved["status"] == {
        "completed_episodes": 2,
        "failed_episodes": 0,
        "invalid_episodes": 0,
        "pending_episodes": 0,
        "planned_episodes": 2,
        "skipped_episodes": 0,
        "started_episodes": 2,
    }

    # Worker count and batching are explicitly operational: they do not alter
    # semantic identity or the canonical output, and may change for recovery.
    resumed = RunCoordinator(ExperimentSpec.from_config(_direct_config(workers=2), seed=79)).run(
        checkpoint_path=checkpoint
    )
    assert resumed == []


def test_resume_does_not_execute_an_episode_already_persisted_before_a_status_crash(
    tmp_path: Path, monkeypatch
) -> None:
    config = tmp_path / "config.yaml"
    _write_config(config)
    store = ArtifactStore(tmp_path / "bundle")
    calls: list[str] = []
    original = EpisodeRunner.run

    def record_calls(self: EpisodeRunner, item):
        calls.append(item.episode_id)
        return original(self, item)

    monkeypatch.setattr(EpisodeRunner, "run", record_calls)

    def inject(phase: str) -> None:
        if phase == "after_status_write":
            raise InjectedCrash(phase)

    with pytest.raises(InjectedCrash):
        run_eval(
            str(config),
            seed=73,
            artifact_store=store,
            checkpoint_path=str(store.run_dir / "checkpoint.json"),
            failure_injector=inject,
        )
    persisted_id = _episodes(store.run_dir)[0].episode_id
    planned_ids = {
        item.episode_id
        for item in normalize_execution_request(ExecutionRequest(config_path=str(config), seed=73)).episodes
    }
    calls_before_resume = list(calls)

    _resume(config, store)
    assert [episode_id for episode_id in calls_before_resume if episode_id in planned_ids] == [persisted_id]
    assert calls.count(persisted_id) == 1
    assert {episode_id for episode_id in calls if episode_id in planned_ids} == planned_ids


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        (lambda saved: saved["normalized_config"].update({"episode_steps": 99}), "checkpoint.normalized_config"),
        (
            lambda saved: saved["scenario_manifest_hashes"][0].update({"content_hash": "0" * 64}),
            "checkpoint.scenario_manifest_hashes",
        ),
        (lambda saved: saved["plugin_descriptors"][0].update({"version": "999"}), "checkpoint.plugin_descriptors"),
        (
            lambda saved: saved["artifact_schema_versions"].update({"episodes": "canonical-jsonl-v0"}),
            "checkpoint.artifact_schema_versions",
        ),
    ],
)
def test_resume_rejects_each_mutated_checkpoint_compatibility_boundary(tmp_path: Path, mutation, field: str) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    spec = ExperimentSpec.from_config(_direct_config(), seed=83)
    RunCoordinator(spec).run(checkpoint_path=checkpoint)
    saved = read_json(checkpoint)
    mutation(saved)
    from tool_agent_shift_benchmark.core.serialization import write_json

    write_json(checkpoint, saved)

    with pytest.raises(IdentityMismatchError) as raised:
        RunCoordinator(spec).run(checkpoint_path=checkpoint)
    assert raised.value.field == field


def test_resume_rejects_policy_resource_or_semantic_identity_change(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    RunCoordinator(ExperimentSpec.from_config(_direct_config(policy_hash="a" * 64), seed=89)).run(
        checkpoint_path=checkpoint
    )

    with pytest.raises(IdentityMismatchError) as raised:
        RunCoordinator(ExperimentSpec.from_config(_direct_config(policy_hash="b" * 64), seed=89)).run(
            checkpoint_path=checkpoint
        )
    assert raised.value.field == "checkpoint.run_id"
