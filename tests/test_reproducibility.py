from tool_agent_shift_benchmark.run_eval import run_eval


def test_reproducible_episode_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    a = [e.episode_id for e in run_eval("small", 42)]
    b = [e.episode_id for e in run_eval("small", 42)]
    assert a == b
