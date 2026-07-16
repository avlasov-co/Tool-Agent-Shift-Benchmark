from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

from tool_agent_shift_benchmark.core.serialization import (
    CanonicalSerializationError,
    canonical_bytes,
    canonical_dumps,
    canonical_loads,
    canonicalize,
    register_dataclass,
    register_enum,
    stable_hash,
    write_json,
    write_jsonl,
)


@register_dataclass
@dataclass(frozen=True)
class RegisteredRecord:
    name: str
    values: tuple[float, ...]


@register_enum
class RegisteredMode(Enum):
    ENABLED = "enabled"


@dataclass(frozen=True)
class UnregisteredRecord:
    value: str


class UnregisteredMode(Enum):
    DISABLED = "disabled"


class UnstableRepresentation:
    def __repr__(self) -> str:
        return f"unstable-{id(self)}"


def test_canonical_serializer_supports_only_declared_values() -> None:
    value = {
        "null": None,
        "bool": True,
        "int": 7,
        "float": 1.25,
        "negative_zero": -0.0,
        "string": "café",
        "mapping": {"z": 1, "a": 2},
        "sequence": ("first", 2, False),
        "record": RegisteredRecord("r", (0.25, 1.0)),
        "enum": RegisteredMode.ENABLED,
    }

    encoded = canonical_dumps(value)
    decoded = canonical_loads(encoded)

    assert encoded.encode("utf-8") == canonical_bytes(value)
    assert '"string":"café"' in encoded
    assert '"negative_zero":-0.0' in encoded
    assert list(decoded["mapping"]) == ["a", "z"]
    assert decoded["record"] == {"name": "r", "values": [0.25, 1.0]}
    assert decoded["enum"] == "enabled"


@pytest.mark.parametrize(
    ("value", "path", "reason"),
    [
        ({"trace": [0.0, math.nan]}, "$.trace[1]", "non-finite"),
        ({"trace": {"score": math.inf}}, "$.trace.score", "non-finite"),
        ({"trace": {"score": -math.inf}}, "$.trace.score", "non-finite"),
        ({"payload": b"bytes"}, "$.payload", "unsupported"),
        ({"payload": {"unordered"}}, "$.payload", "unsupported"),
        ({"payload": UnstableRepresentation()}, "$.payload", "unsupported"),
        ({"payload": Path("relative")}, "$.payload", "unsupported"),
        ({"payload": UnregisteredRecord("x")}, "$.payload", "not registered"),
        ({"payload": UnregisteredMode.DISABLED}, "$.payload", "not registered"),
        ({1: "non-string-key"}, "$", "mapping keys"),
    ],
)
def test_unsupported_values_fail_with_exact_paths(value: Any, path: str, reason: str) -> None:
    with pytest.raises(CanonicalSerializationError) as raised:
        canonical_dumps(value)

    assert raised.value.path == path
    assert reason in raised.value.reason


def test_non_finite_json_input_is_rejected() -> None:
    with pytest.raises(CanonicalSerializationError, match="non-finite JSON constants"):
        canonical_loads('{"score":NaN}')


def test_canonical_writers_use_deterministic_utf8_and_newlines(tmp_path: Path) -> None:
    json_path = tmp_path / "record.json"
    jsonl_path = tmp_path / "records.jsonl"
    record = {"z": "é", "a": 1.0}

    write_json(json_path, record)
    write_jsonl(jsonl_path, [record, {"a": 2.0, "z": "ß"}])

    assert json_path.read_bytes().endswith(b"\n")
    assert b"\xc3\xa9" in json_path.read_bytes()
    assert json.loads(json_path.read_text(encoding="utf-8")) == record
    lines = jsonl_path.read_bytes().splitlines()
    assert lines[0] == canonical_bytes(record)
    assert lines[1] == canonical_bytes({"a": 2.0, "z": "ß"})


def _nested_value(rng: random.Random, depth: int = 0) -> Any:
    leaves: list[Any] = [None, True, False, rng.randint(-(2**70), 2**70), rng.uniform(-1000, 1000), "é"]
    if depth >= 4 or rng.random() < 0.45:
        return rng.choice(leaves)
    if rng.random() < 0.5:
        return [_nested_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    keys = [f"key_{depth}_{index}" for index in range(rng.randint(0, 4))]
    rng.shuffle(keys)
    return {key: _nested_value(rng, depth + 1) for key in keys}


def test_property_style_nested_structures_round_trip_and_hash_stably() -> None:
    rng = random.Random(20260716)
    for _ in range(200):
        value = _nested_value(rng)
        encoded = canonical_dumps(value)
        decoded = canonical_loads(encoded)
        assert decoded == canonicalize(value)
        assert stable_hash(decoded) == stable_hash(value)


def test_mapping_insertion_order_does_not_change_hash_but_list_order_does() -> None:
    first = {"outer": {"b": 2, "a": 1}, "ordered": [1, 2]}
    reordered_map = {"ordered": [1, 2], "outer": {"a": 1, "b": 2}}
    reordered_list = {"outer": {"a": 1, "b": 2}, "ordered": [2, 1]}

    assert stable_hash(first) == stable_hash(reordered_map)
    assert stable_hash(first) != stable_hash(reordered_list)


def test_hash_is_stable_across_processes_and_working_directories(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    first_dir = tmp_path / "one"
    second_dir = tmp_path / "two"
    first_dir.mkdir()
    second_dir.mkdir()
    script = (
        "from tool_agent_shift_benchmark.core.serialization import stable_hash; "
        "print(stable_hash({'unicode':'é','float':1.25,'nested':[{'b':2,'a':1}]}, prefix='test'))"
    )
    environment = {**os.environ, "PYTHONPATH": str(repository)}

    first = subprocess.run(
        [sys.executable, "-c", script],
        cwd=first_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    second = subprocess.run(
        [sys.executable, "-c", script],
        cwd=second_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert first == second == stable_hash({"unicode": "é", "float": 1.25, "nested": [{"b": 2, "a": 1}]}, prefix="test")


def test_planned_filtered_replay_and_resume_identity_is_cross_process_stable(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    first_dir = tmp_path / "worker-one"
    second_dir = tmp_path / "worker-three"
    first_dir.mkdir()
    second_dir.mkdir()
    script = """
import os
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.serialization import canonical_dumps
config = {
    'schema_version': 2,
    'environments': ['file_ops'],
    'agents': ['naive'],
    'faults': ['normal'],
    'episodes_per_combo': 3,
    'episode_steps': 1,
    '_working_directory': os.getcwd(),
}
workers = int(os.environ['TEST_WORKERS'])
catalog = PluginCatalog(include_external=False)
spec = ExperimentSpec.from_config(config, seed=37, workers=workers)
planner = ExperimentPlanner(spec, catalog)
plan = planner.plan()
target = plan[1].episode_id
manifest_dir = os.path.join(os.getcwd(), 'scenarios')
RunCoordinator(spec, catalog).run(scenario_manifest_dir=manifest_dir)
filtered = ExperimentPlanner(
    ExperimentSpec.from_config(config, seed=37, workers=workers, episode_ids=[target]), catalog
).plan()
replay = ExperimentPlanner(
    ExperimentSpec.from_config(
        {**config, 'scenario_manifest_path': manifest_dir},
        seed=37,
        workers=workers,
        replay_episode_ids=[target],
    ), catalog
).plan()
resumed = RunCoordinator(spec, catalog).run({target})
print(canonical_dumps({
    'run_id': planner.run_id,
    'plan': [item.episode_id for item in plan],
    'filtered': [item.episode_id for item in filtered],
    'replay': [item.episode_id for item in replay],
    'resumed': [episode.episode_id for episode in resumed],
}))
"""
    environment = {**os.environ, "PYTHONPATH": str(repository)}

    outputs = []
    for directory, workers in ((first_dir, "1"), (second_dir, "3")):
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=directory,
            env={**environment, "TEST_WORKERS": workers},
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(result.stdout.strip())

    assert outputs[0] == outputs[1]
