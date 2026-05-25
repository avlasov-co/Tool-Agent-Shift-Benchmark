from src.run_eval import run_eval
from src.metrics.aggregation import aggregate


def test_metrics_count_unsafe_actions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import shutil, pathlib
    srcroot = pathlib.Path(__file__).resolve().parents[1]
    shutil.copytree(srcroot / "configs", tmp_path / "configs")
    episodes = run_eval("configs/small.yaml", 42, env="file_ops", agent="naive")
    rows = aggregate(episodes)
    assert rows
    assert any(r["unsafe_action_rate"] > 0 for r in rows)
    assert (tmp_path / "results" / "summary.csv").exists()
