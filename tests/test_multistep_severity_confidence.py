import csv
import json
from pathlib import Path

from tool_agent_shift_benchmark.agents.offline_llm_fixture import OfflineLLMFixtureAgent
from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.faults.stale_observation import StaleObservationFault
from tool_agent_shift_benchmark.run_eval import run_eval
from tool_agent_shift_benchmark.run_seeds import run_seeds


def test_multistep_and_severity_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    episodes = run_eval("small", seed=7, all_envs=False, all_agents=False)
    assert episodes
    assert Path("results/multistep_traces.jsonl").exists()
    rows = list(csv.DictReader(open("results/episode_log.csv", encoding="utf-8")))
    assert "episode_steps" in rows[0]
    assert "fault_severity" in rows[0]
    assert any(float(r["fault_severity"]) == 0.5 for r in rows if r["fault_name"] != "normal")
    first_trace = json.loads(Path("results/multistep_traces.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "step_trace" in first_trace


def test_fault_severity_changes_latency_or_staleness():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    response = env.tool_response()
    low = StaleObservationFault(severity=0.5).apply(response, env, __import__("random").Random(1))
    high = StaleObservationFault(severity=1.0).apply(response, env, __import__("random").Random(1))
    assert high.observation.timestamp < low.observation.timestamp


def test_run_seeds_confidence_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_rows, ci_rows = run_seeds("seeds", all_envs=False, all_agents=False)
    assert seed_rows
    assert ci_rows
    assert Path("results/seed_summary.csv").exists()
    assert Path("results/confidence_intervals.csv").exists()


def test_offline_fixture_has_no_network_dependency():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    agent = OfflineLLMFixtureAgent()
    response = env.tool_response()
    decision = agent.decide(ObservationContext.from_environment(env, response.observation), response)
    assert decision.agent_name == "offline_llm_fixture"
    assert decision.metadata["network_calls"] == 0
