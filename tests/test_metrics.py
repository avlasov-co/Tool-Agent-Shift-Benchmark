from tool_agent_shift_benchmark.metrics.aggregation import aggregate
from tool_agent_shift_benchmark.run_eval import run_eval


def test_metrics_count_unsafe_actions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    episodes = run_eval("small", 42, env="file_ops", agent="naive")
    rows = aggregate(episodes)
    assert rows
    assert any(r["unsafe_action_rate"] > 0 for r in rows)
    assert (tmp_path / "results" / "summary.csv").exists()
