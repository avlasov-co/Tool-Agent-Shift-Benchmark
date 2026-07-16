from __future__ import annotations

import json
from pathlib import Path

import pytest

from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.contracts import PluginDescriptor
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.run_artifacts import prepare_run_dir, snapshot_outputs
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision


class VisibleOnlyAgent:
    name = "visible_only"

    def decide(self, context, response):
        assert not hasattr(context, "environment")
        assert "faults" not in response.observation.metadata
        assert "ground_truth" not in response.metadata
        return AgentDecision(self.name, AgentAction("abstain", abstain=True), 1.0)


def catalog_with_agent(agent):
    catalog = PluginCatalog(include_external=False)
    catalog.register(PluginDescriptor("agent", agent.name, version="test"), agent)
    return catalog


def config_v2(config):
    normalized = {"schema_version": 2, **config}
    references = []
    builtins = {"naive", "retry", "validate_then_act", "monitor_gated", "conservative", "offline_llm_fixture"}
    for agent in normalized.get("agents", []):
        if agent not in builtins:
            references.append(
                {
                    "kind": "agent",
                    "name": agent,
                    "version": "test",
                    "contract_version": "1",
                    "entry_point": f"tests:{agent}",
                }
            )
    if references:
        normalized["plugin_references"] = references
    return normalized


def test_custom_agent_gets_only_policy_visible_state():
    catalog = catalog_with_agent(VisibleOnlyAgent)
    spec = ExperimentSpec.from_config(
        config_v2(
            {
                "environments": ["file_ops"],
                "agents": ["visible_only"],
                "faults": ["schema_drift"],
                "episodes_per_combo": 1,
            }
        ),
        seed=3,
    )
    episode = RunCoordinator(spec, catalog).run()[0]
    assert episode.decision.action.abstain
    assert episode.metadata["evaluator_trace"][0]["hidden_ground_truth"]
    assert "faults" not in episode.metadata["step_trace"][0]["tool_response"]["observation"]["metadata"]


def test_entry_point_plugin_is_discovered_and_invalid_contract_is_rejected(monkeypatch):
    class ExternalAgent(VisibleOnlyAgent):
        name = "external_visible"

    ExternalAgent.plugin_descriptor = PluginDescriptor("agent", "external_visible", version="2.0.0")

    class EntryPoint:
        name = "external_visible"

        def load(self):
            return ExternalAgent

    class EntryPoints:
        def select(self, *, group):
            return [EntryPoint()] if group == "tasb.agents" else []

    monkeypatch.setattr("tool_agent_shift_benchmark.core.catalog.entry_points", lambda: EntryPoints())
    catalog = PluginCatalog()
    assert catalog.descriptor("agent", "external_visible").version == "2.0.0"
    assert catalog.get("agent", "external_visible") is ExternalAgent

    class BadEntryPoint(EntryPoint):
        name = "bad_external"

        def load(self):
            class Bad:
                plugin_descriptor = PluginDescriptor("agent", "bad_external", contract_version="999")

            return Bad

    class BadEntryPoints(EntryPoints):
        def select(self, *, group):
            return [BadEntryPoint()] if group == "tasb.agents" else []

    monkeypatch.setattr("tool_agent_shift_benchmark.core.catalog.entry_points", lambda: BadEntryPoints())
    with pytest.raises(ValueError, match="incompatible contract"):
        PluginCatalog()


def test_resume_skips_completed_episode_specs_without_duplicates():
    config = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["normal"],
        "episodes_per_combo": 3,
    }
    spec = ExperimentSpec.from_config(config, seed=11)
    catalog = PluginCatalog(include_external=False)
    planner = ExperimentPlanner(spec, catalog)
    plan = planner.plan()
    first = RunCoordinator(spec, catalog).run()
    resumed = RunCoordinator(spec, catalog).run({plan[0].episode_id})
    assert len(first) == 3
    assert len(resumed) == 2
    assert plan[0].episode_id not in {episode.episode_id for episode in resumed}


def test_retryable_plugin_failure_is_not_an_unsafe_episode():
    class FlakyAgent:
        name = "flaky"
        attempts = 0

        def decide(self, context, response):
            type(self).attempts += 1
            if type(self).attempts == 1:
                raise RuntimeError("temporary plugin failure")
            return AgentDecision(self.name, AgentAction("abstain", abstain=True), 1.0)

    catalog = catalog_with_agent(FlakyAgent)
    spec = ExperimentSpec.from_config(
        config_v2(
            {
                "environments": ["file_ops"],
                "agents": ["flaky"],
                "faults": ["normal"],
                "episodes_per_combo": 1,
                "retry_attempts": 1,
            }
        ),
        seed=4,
    )
    result = RunCoordinator(spec, catalog).run()
    assert len(result) == 1
    assert not result[0].execution.unsafe


def test_failure_policy_distinguishes_orchestration_errors_from_episode_results():
    class BrokenAgent:
        name = "broken"

        def decide(self, context, response):
            raise RuntimeError("broken plugin")

    catalog = catalog_with_agent(BrokenAgent)
    base = config_v2(
        {
            "environments": ["file_ops"],
            "agents": ["broken"],
            "faults": ["normal"],
            "episodes_per_combo": 1,
        }
    )
    coordinator = RunCoordinator(ExperimentSpec.from_config({**base, "failure_policy": "continue"}), catalog)
    assert coordinator.run() == []
    assert coordinator.errors[0].error_type == "RuntimeError"
    with pytest.raises(RuntimeError):
        RunCoordinator(ExperimentSpec.from_config({**base, "failure_policy": "fail_fast"}), catalog).run()


def test_run_manifest_checksums_cover_bundle_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("results").mkdir()
    Path("results/episodes.jsonl").write_text('{"episode_id":"ep1"}\n', encoding="utf-8")
    run_dir = prepare_run_dir("bundle", overwrite=True)
    manifest = snapshot_outputs(run_dir)
    for relative, checksum in manifest["checksums"].items():
        import hashlib

        assert hashlib.sha256((run_dir / relative).read_bytes()).hexdigest() == checksum
    assert (run_dir / "config.json").exists() is False or (run_dir / "config.json").is_file()


def test_structured_episode_round_trip():
    spec = ExperimentSpec.from_config(
        config_v2(
            {
                "environments": ["file_ops"],
                "agents": ["naive"],
                "faults": ["normal"],
                "episodes_per_combo": 1,
            }
        ),
        seed=9,
    )
    episode = RunCoordinator(spec).run()[0]
    restored = Episode.from_dict(json.loads(json.dumps(episode.to_dict())))
    assert restored.episode_id == episode.episode_id
    assert restored.to_row() == episode.to_row()
