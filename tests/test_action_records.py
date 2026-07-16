from __future__ import annotations

import json
from pathlib import Path

import pytest

from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.contracts import PluginDescriptor
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.run_artifacts import prepare_run_dir, snapshot_outputs
from tool_agent_shift_benchmark.core.serialization import read_csv, read_json
from tool_agent_shift_benchmark.core.types import MonitorDecision
from tool_agent_shift_benchmark.reporting.failure_cases import replay_case
from tool_agent_shift_benchmark.run_eval import run_eval


def config(
    *,
    agent: str = "naive",
    fault: str = "normal",
    oversight: str = "hard_gate",
    monitor: str = "composite",
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": [agent],
        "faults": [fault],
        "fault_severities": [1.0],
        "episodes_per_combo": 1,
        "episode_steps": 6,
        "oversight_modes": [oversight],
        "monitor": monitor,
    }
    if monitor != "composite":
        value["plugin_references"] = [
            {
                "kind": "monitor",
                "name": monitor,
                "version": "test",
                "contract_version": "1",
                "entry_point": f"tests:{monitor}",
            }
        ]
    return value


class BlockMoveMonitor:
    name = "block_move"

    def check(self, context, observation, action):
        denied = action.action_type == "move"
        return MonitorDecision(self.name, not denied, 1.0 if denied else 0.0, ["move_denied"] if denied else [])


class AlwaysBlockMonitor:
    name = "always_block_action_record"

    def check(self, context, observation, action):
        return MonitorDecision(self.name, False, 1.0, ["always_block"])


def catalog_with_monitor(name: str, monitor: type[object]) -> PluginCatalog:
    catalog = PluginCatalog(include_external=False)
    catalog.register(PluginDescriptor("monitor", name, version="test"), monitor)
    return catalog


def shifted_episode_with_monitor(name: str, monitor: type[object], *, fault: str):
    episodes = RunCoordinator(
        ExperimentSpec.from_config(config(fault=fault, monitor=name), seed=137),
        catalog_with_monitor(name, monitor),
    ).run()
    return next(episode for episode in episodes if episode.fault.name == fault)


def test_allowed_safe_actions_have_immutable_complete_records() -> None:
    episode = RunCoordinator(ExperimentSpec.from_config(config(), seed=137)).run()[0]

    assert episode.episode_record_version == "3"
    assert len(episode.action_records) == episode.metadata["steps_taken"]
    assert episode.action_records[-1].stop_reason == "completed"
    assert all(record.status == "complete" for record in episode.action_records)
    assert all(
        record.proposed_action.action_hash == record.executed_action.action_hash for record in episode.action_records
    )
    assert all(record.intervention.intervention_type == "allowed" for record in episode.action_records)
    assert episode.action_records[-1].execution_result.success
    assert "hidden_ground_truth" in episode.action_records[-1].evaluator_labels
    assert all("evaluator_labels" not in step["action_record"] for step in episode.metadata["step_trace"])
    assert all("execution_result" not in step["action_record"] for step in episode.metadata["step_trace"])
    with pytest.raises(TypeError):
        episode.action_records[0].proposed_action.params["mutate"] = True


def test_blocked_unsafe_proposal_preserves_proposal_and_transforms_only_execution() -> None:
    episode = shifted_episode_with_monitor("block_move", BlockMoveMonitor, fault="stale_observation")
    blocked = next(record for record in episode.action_records if record.intervention.blocked)

    assert blocked.proposed_action.action_type == "move"
    assert blocked.executed_action.action_type == "abstain"
    assert blocked.intervention.intervention_type == "block_to_abstain"
    assert blocked.intervention.transformed
    assert blocked.intervention.proposal_preserved
    assert blocked.execution_result.unsafe is False
    assert episode.decision.action.action_type == "move"
    assert episode.execution.metadata["abstained"] is True


def test_blocked_safe_proposal_is_distinct_from_agent_abstention() -> None:
    blocked = shifted_episode_with_monitor(
        "always_block_action_record",
        AlwaysBlockMonitor,
        fault="normal",
    ).action_records[0]
    abstained_episode = next(
        episode
        for episode in RunCoordinator(
            ExperimentSpec.from_config(
                config(agent="conservative", fault="stale_observation", oversight="record_only"),
                seed=137,
            )
        ).run()
        if episode.fault.name == "stale_observation"
    )
    abstained = abstained_episode.action_records[0]

    assert blocked.proposed_action.action_type == "inspect_files"
    assert blocked.executed_action.action_type == "abstain"
    assert blocked.intervention.blocked
    assert abstained.proposed_action.abstain
    assert abstained.executed_action.action_hash == abstained.proposed_action.action_hash
    assert abstained.intervention.intervention_type == "recorded_only"
    assert abstained.intervention.intervened is False


def test_episode_reader_reconstructs_one_legacy_aggregate_action_record() -> None:
    episode = RunCoordinator(ExperimentSpec.from_config(config(), seed=151)).run()[0]
    payload = episode.to_dict()
    payload.pop("episode_record_version")
    payload.pop("action_records")

    restored = Episode.from_dict(payload)

    assert restored.episode_record_version == "2"
    assert len(restored.action_records) == 1
    assert restored.action_records[0].status == "legacy_reconstructed"
    assert restored.action_records[0].proposed_action.action_type == episode.decision.action.action_type


class FailingAgent:
    name = "failing_action_record_agent"

    def decide(self, context, response):
        raise RuntimeError("agent infrastructure failed before proposal")


def test_infrastructure_failure_gets_a_non_fabricated_failure_record() -> None:
    catalog = PluginCatalog(include_external=False)
    catalog.register(PluginDescriptor("agent", FailingAgent.name, version="test"), FailingAgent)
    value = config(agent=FailingAgent.name)
    value["plugin_references"] = [
        {
            "kind": "agent",
            "name": FailingAgent.name,
            "version": "test",
            "contract_version": "1",
            "entry_point": "tests:failing_action_record_agent",
        }
    ]
    coordinator = RunCoordinator(ExperimentSpec.from_config(value, seed=157), catalog)

    assert coordinator.run() == []
    failure = coordinator.errors[0].action_record
    assert failure["status"] == "infrastructure_failure"
    assert failure["proposed_action"] is None
    assert failure["executed_action"] is None
    assert failure["evaluator_labels"]["error_type"] == "RuntimeError"


def test_action_records_are_exported_checkpointed_manifested_and_replayable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "records.yaml"
    config_path.write_text(
        """\
schema_version: 2
environments: [file_ops]
agents: [naive]
faults: [stale_observation]
fault_severities: [1.0]
episodes_per_combo: 1
episode_steps: 6
oversight_modes: [record_only]
""",
        encoding="utf-8",
    )
    episodes = run_eval(str(config_path), 163)
    action_rows = read_csv(tmp_path / "results" / "action_records.csv")
    checkpoint = tmp_path / "checkpoint.json"
    RunCoordinator(ExperimentSpec.from_config(config(fault="normal"), seed=167)).run(checkpoint_path=checkpoint)
    checkpoint_payload = read_json(checkpoint)
    run_dir = prepare_run_dir("action-records", runs_dir=tmp_path / "runs")
    manifest = snapshot_outputs(run_dir, command=["tasb", "run"])
    failure_rows = read_csv(tmp_path / "results" / "failure_cases.csv")
    replay = replay_case(failure_rows[0]["case_id"], str(tmp_path / "results" / "failure_cases.csv"))

    assert len(action_rows) == sum(len(episode.action_records) for episode in episodes)
    assert {row["intervention_type"] for row in action_rows} == {"recorded_only"}
    assert (tmp_path / "results" / "action_records.jsonl").exists()
    first_jsonl = json.loads((tmp_path / "results" / "action_records.jsonl").read_text().splitlines()[0])
    assert first_jsonl["action_record"]["contract"] == "action-record-v1"
    assert checkpoint_payload["episode_record_version"] == "3"
    assert checkpoint_payload["action_record_contract"] == "action-record-v1"
    assert checkpoint_payload["counterfactual_evaluation_contract"] == "counterfactual-evaluation-v1"
    assert manifest["episode_record_version"] == "3"
    assert manifest["action_record_contract"] == "action-record-v1"
    assert manifest["counterfactual_evaluation_contract"] == "counterfactual-evaluation-v1"
    assert action_rows[0]["execution_equivalent"] == "True"
    assert replay["proposed_action_type"]
    assert replay["executed_action_type"]
    assert replay["intervention_type"] == "recorded_only"
