from random import Random

import pytest

from src.agents import AGENTS
from src.core.context import ObservationContext, redact_response_for_policy
from src.environments.file_ops import FileOpsEnvironment
from src.core.types import Observation, ToolResponse
from src.faults import FAULTS
from src.monitors.composite import CompositeMonitor


def test_redact_response_for_policy_removes_evaluator_only_metadata():
    obs = Observation(
        env_name="file_ops",
        scenario_id="case",
        timestamp=10,
        data={"files": []},
        metadata={"faults": [{"name": "schema_drift"}], "memory_hint": "visible_hint"},
    )
    resp = ToolResponse(
        tool_name="list_files",
        ok=True,
        observation=obs,
        metadata={
            "faults": ["schema_drift"],
            "ground_truth": {"secret": True},
            "score": 1,
            "labels": ["unsafe"],
            "public_note": "visible",
        },
    )

    redacted = redact_response_for_policy(resp)

    assert "faults" not in redacted.observation.metadata
    assert redacted.observation.metadata["memory_hint"] == "visible_hint"
    assert redacted.metadata == {"public_note": "visible"}
    assert "faults" in resp.observation.metadata
    assert "ground_truth" in resp.metadata


def test_offline_fixture_ignores_evaluator_fault_labels_after_redaction():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    clean = env.tool_response()
    labeled_only = ToolResponse(
        tool_name=clean.tool_name,
        ok=clean.ok,
        observation=Observation(
            env_name=clean.observation.env_name,
            scenario_id=clean.observation.scenario_id,
            timestamp=clean.observation.timestamp,
            data=clean.observation.data,
            schema_version=clean.observation.schema_version,
            constraints=clean.observation.constraints,
            metadata={**clean.observation.metadata, "faults": [{"name": "stale_observation"}]},
        ),
        latency_ms=clean.latency_ms,
        errors=clean.errors,
        metadata={"faults": ["stale_observation"]},
    )
    visible_labeled = redact_response_for_policy(labeled_only)
    clean_ctx = ObservationContext.from_environment(env, clean.observation)
    visible_ctx = ObservationContext.from_environment(env, visible_labeled.observation)

    clean_decision = AGENTS["offline_llm_fixture"]().decide(clean_ctx, clean)
    visible_decision = AGENTS["offline_llm_fixture"]().decide(visible_ctx, visible_labeled)

    assert "faults" not in visible_labeled.observation.metadata
    assert "faults" not in visible_labeled.metadata
    assert clean_decision.reasons == visible_decision.reasons
    assert clean_decision.action.action_type == visible_decision.action.action_type


def test_agents_receive_redacted_response_in_boundary_test():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    faulted = FAULTS["schema_drift"]().apply(env.tool_response(), env, Random(1))
    visible = redact_response_for_policy(faulted)
    ctx = ObservationContext.from_environment(env, visible.observation)

    for cls in AGENTS.values():
        decision = cls().decide(ctx, visible)
        assert decision.agent_name == cls.name
        assert "faults" not in visible.observation.metadata
        monitor_decision = CompositeMonitor().check(ctx, visible.observation, decision.action)
        assert monitor_decision.monitor_name == "composite_monitor"


def test_observation_context_exposes_only_visible_surface():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["stale_observation"]().apply(env.tool_response(), env, Random(1))
    ctx = ObservationContext.from_environment(env, resp.observation)
    assert not hasattr(ctx, "hidden_ground_truth")
    assert not hasattr(ctx, "tool_response")
    assert not hasattr(ctx, "execute")
    assert not hasattr(ctx, "_env")
    assert not hasattr(ctx, "__dict__")
    with pytest.raises(AttributeError):
        getattr(ctx, "hidden_ground_truth")


def test_all_agents_and_monitors_run_without_environment_object():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    faulted = FAULTS["missing_field"]().apply(env.tool_response(), env, Random(1))
    resp = redact_response_for_policy(faulted)
    ctx = ObservationContext.from_environment(env, resp.observation)
    for cls in AGENTS.values():
        agent = cls()
        decision = agent.decide(ctx, resp)
        assert decision.agent_name == agent.name
        monitor_decision = CompositeMonitor().check(ctx, resp.observation, decision.action)
        assert monitor_decision.monitor_name == "composite_monitor"


def test_run_eval_redacts_evaluator_fault_labels_from_policy_inputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import shutil
    import pathlib
    from src.core.types import AgentAction, AgentDecision
    from src.run_eval import run_eval
    import src.run_eval as run_eval_module

    srcroot = pathlib.Path(__file__).resolve().parents[1]
    shutil.copytree(srcroot / "configs", tmp_path / "configs")

    class SpyAgent:
        name = "spy"

        def decide(self, context, response):
            assert "faults" not in response.observation.metadata
            assert "faults" not in response.metadata
            return AgentDecision(self.name, AgentAction("abstain", abstain=True, reason="spy_done"), 0.5)

    monkeypatch.setitem(run_eval_module.AGENTS, "spy", SpyAgent)
    episodes = run_eval("configs/small.yaml", 42, env="file_ops", agent="spy")
    assert episodes
    assert any(e.tool_response.observation.metadata.get("faults") for e in episodes if e.fault.name != "normal")


def test_single_seed_run_records_effective_config_and_clears_stale_ci(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import json
    import shutil
    import pathlib
    from src.run_eval import run_eval

    srcroot = pathlib.Path(__file__).resolve().parents[1]
    shutil.copytree(srcroot / "configs", tmp_path / "configs")
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "confidence_intervals.csv").write_text("stale\n", encoding="utf-8")
    (tmp_path / "results" / "seed_summary.csv").write_text("stale\n", encoding="utf-8")

    episodes = run_eval("configs/small.yaml", 42, all_envs=True, all_agents=True)
    cfg = json.loads((tmp_path / "results" / "config.json").read_text(encoding="utf-8"))["config"]
    assert len(episodes) == 252
    assert cfg["effective_environments"] == ["file_ops", "calendar_ops", "risk_ops"]
    assert "conservative" in cfg["effective_agents"]
    assert not (tmp_path / "results" / "confidence_intervals.csv").exists()
    assert not (tmp_path / "results" / "seed_summary.csv").exists()
