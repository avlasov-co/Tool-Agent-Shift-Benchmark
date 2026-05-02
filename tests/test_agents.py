from random import Random

from src.agents import AGENTS
from src.core.context import ObservationContext
from src.environments.file_ops import FileOpsEnvironment
from src.faults import FAULTS


def _context(env, resp):
    return ObservationContext.from_environment(env, resp.observation)


def test_common_interface_and_different_behavior():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["stale_observation"]().apply(env.tool_response(), env, Random(1))
    ctx = _context(env, resp)
    decisions = {name: cls().decide(ctx, resp) for name, cls in AGENTS.items()}
    assert all(hasattr(d, "action") for d in decisions.values())
    assert decisions["naive"].action.abstain is False
    assert decisions["conservative"].action.abstain is True


def test_retry_agent_does_not_bypass_fault_with_clean_tool_response():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["schema_drift"]().apply(env.tool_response(), env, Random(1))
    ctx = _context(env, resp)

    def forbidden_clean_retry():  # would be evaluator leakage after fault injection
        raise AssertionError("agent attempted clean tool_response bypass")

    env.tool_response = forbidden_clean_retry
    d = AGENTS["retry"]().decide(ctx, resp)
    assert d.action.abstain
    assert d.metadata["retry"] is False
    assert d.metadata["clean_tool_bypass_prevented"] is True


def test_validate_blocks_invalid_outputs():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["schema_drift"]().apply(env.tool_response(), env, Random(1))
    d = AGENTS["validate_then_act"]().decide(_context(env, resp), resp)
    assert d.action.abstain


def test_monitor_gated_follows_monitor_decision():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["stale_observation"]().apply(env.tool_response(), env, Random(1))
    agent = AGENTS["monitor_gated"]()
    d = agent.decide(_context(env, resp), resp)
    assert d.action.abstain
    assert agent.last_monitor_decision is not None


def test_naive_can_produce_unsafe_under_faults():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["stale_observation"]().apply(env.tool_response(), env, Random(1))
    d = AGENTS["naive"]().decide(_context(env, resp), resp)
    result = env.execute(d.action, resp.observation.timestamp)
    assert result.unsafe
