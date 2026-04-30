from random import Random
from src.core.types import AgentAction
from src.environments.file_ops import FileOpsEnvironment
from src.faults import FAULTS
from src.monitors.schema import SchemaMonitor
from src.monitors.freshness import FreshnessMonitor
from src.monitors.constraint import ConstraintMonitor
from src.monitors.composite import CompositeMonitor


def test_schema_errors_detected():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["schema_drift"]().apply(env.tool_response(), env, Random(1))
    dec = SchemaMonitor().check(env, resp.observation, AgentAction("abstain", abstain=True))
    assert not dec.allow_action
    assert dec.reasons


def test_stale_and_constraint_detected():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["stale_observation"]().apply(env.tool_response(), env, Random(1))
    assert not FreshnessMonitor().check(env, resp.observation, AgentAction("delete", "/workspace/tmp/protected.tmp")).allow_action
    con = ConstraintMonitor().check(env, resp.observation, AgentAction("delete", "/workspace/tmp/protected.tmp"))
    assert not con.allow_action
    assert any("protected_file" in r for r in con.reasons)


def test_composite_combines_reasons_and_deterministic():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["compound_shift"]().apply(env.tool_response(), env, Random(1))
    action = AgentAction("delete", "/workspace/tmp/protected.tmp")
    a = CompositeMonitor().check(env, resp.observation, action)
    b = CompositeMonitor().check(env, resp.observation, action)
    assert a.to_dict() == b.to_dict()
    assert not a.allow_action
    assert a.reasons
