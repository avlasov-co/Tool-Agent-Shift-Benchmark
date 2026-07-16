from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.metrics.aggregation import aggregate
from tool_agent_shift_benchmark.run_eval import run_eval


def test_metrics_count_unsafe_actions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    store = ArtifactStore(tmp_path / "run")
    episodes = run_eval("small", 42, env="file_ops", agent="naive", artifact_store=store)
    rows = aggregate(episodes)
    assert rows
    assert any(r["unsafe_action_rate"] > 0 for r in rows)
    assert (store.run_dir / "results" / "summary.csv").exists()
