from __future__ import annotations

import importlib.util
import sys

import pytest


def _load_rehearsal():
    path = __import__("pathlib").Path(__file__).parents[1] / "scripts" / "release_rehearsal.py"
    spec = importlib.util.spec_from_file_location("release_rehearsal", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_rehearsal_refuses_output_below_source_root(tmp_path) -> None:
    rehearsal = _load_rehearsal()
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(rehearsal.RehearsalError, match="outside the source root"):
        rehearsal.run_rehearsal(source, source / "recursive-output", sys.executable)
