from random import Random

from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment
from tool_agent_shift_benchmark.faults import FAULTS


def test_stale_observation_differs_from_ground_truth():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["stale_observation"]().apply(env.tool_response(), env, Random(1))
    assert resp.observation.timestamp < env.current_time
    assert env.hidden_ground_truth()["files"] != resp.observation.data["files"]


def test_schema_drift_and_missing_field():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    drifted = FAULTS["schema_drift"]().apply(env.tool_response(), env, Random(1))
    assert "items" in drifted.observation.data and "files" not in drifted.observation.data
    missing = FAULTS["missing_field"]().apply(env.tool_response(), env, Random(1))
    removed = missing.observation.metadata["faults"][-1]["details"]["removed_paths"]
    assert removed
    assert all(path.startswith("files[") for path in removed)


def test_every_fault_deterministic_logs_metadata_and_preserves_ground_truth():
    for name, cls in FAULTS.items():
        env1 = RiskOpsEnvironment(seed=7, scenario_index=1)
        gt = env1.hidden_ground_truth()
        a = cls().apply(env1.tool_response(), env1, Random(123)).to_dict()
        env2 = RiskOpsEnvironment(seed=7, scenario_index=1)
        b = cls().apply(env2.tool_response(), env2, Random(123)).to_dict()
        assert a == b
        assert env1.hidden_ground_truth() == gt
        assert "faults" in a["observation"]["metadata"]


def test_compound_combines_multiple_faults_and_latency_recorded():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["compound_shift"]().apply(env.tool_response(), env, Random(1))
    names = [f["name"] for f in resp.observation.metadata["faults"]]
    assert "compound_shift" in names
    assert "stale_observation" in names
    assert resp.latency_ms > 0
