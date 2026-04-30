from src.agents import AGENTS
from src.environments.file_ops import FileOpsEnvironment
from src.faults import FAULTS
from random import Random


def test_common_interface_and_different_behavior():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["stale_observation"]().apply(env.tool_response(), env, Random(1))
    decisions = {name: cls().decide(env, resp) for name, cls in AGENTS.items()}
    assert all(hasattr(d, "action") for d in decisions.values())
    assert decisions["naive"].action.abstain is False
    assert decisions["conservative"].action.abstain is True


def test_retry_agent_retries_invalid_outputs():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["schema_drift"]().apply(env.tool_response(), env, Random(1))
    d = AGENTS["retry"]().decide(env, resp)
    assert d.metadata["retry"] is True


def test_validate_blocks_invalid_outputs():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["schema_drift"]().apply(env.tool_response(), env, Random(1))
    d = AGENTS["validate_then_act"]().decide(env, resp)
    assert d.action.abstain


def test_monitor_gated_follows_monitor_decision():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["stale_observation"]().apply(env.tool_response(), env, Random(1))
    agent = AGENTS["monitor_gated"]()
    d = agent.decide(env, resp)
    assert d.action.abstain
    assert agent.last_monitor_decision is not None


def test_naive_can_produce_unsafe_under_faults():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["stale_observation"]().apply(env.tool_response(), env, Random(1))
    d = AGENTS["naive"]().decide(env, resp)
    result = env.execute(d.action, resp.observation.timestamp)
    assert result.unsafe
