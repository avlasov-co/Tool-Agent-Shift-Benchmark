from src.run_eval import run_eval


def test_reproducible_episode_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import shutil, pathlib
    srcroot = pathlib.Path(__file__).resolve().parents[1]
    shutil.copytree(srcroot / "configs", tmp_path / "configs")
    a = [e.episode_id for e in run_eval("configs/small.yaml", 42)]
    b = [e.episode_id for e in run_eval("configs/small.yaml", 42)]
    assert a == b
