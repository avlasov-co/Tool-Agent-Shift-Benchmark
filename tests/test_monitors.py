from random import Random

from src.core.context import ObservationContext
from src.core.types import AgentAction
from src.environments.file_ops import FileOpsEnvironment
from src.faults import FAULTS
from src.monitors.schema import SchemaMonitor
from src.monitors.freshness import FreshnessMonitor
from src.monitors.constraint import ConstraintMonitor
from src.monitors.composite import CompositeMonitor


def _context(env, resp):
    return ObservationContext.from_environment(env, resp.observation)


def test_schema_errors_detected():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["schema_drift"]().apply(env.tool_response(), env, Random(1))
    dec = SchemaMonitor().check(_context(env, resp), resp.observation, AgentAction("abstain", abstain=True))
    assert not dec.allow_action
    assert dec.reasons


def test_stale_detected_without_hidden_constraint_leakage():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["stale_observation"]().apply(env.tool_response(), env, Random(1))
    ctx = _context(env, resp)
    action = AgentAction("delete", "/workspace/tmp/protected.tmp")
    assert not FreshnessMonitor().check(ctx, resp.observation, action).allow_action
    con = ConstraintMonitor().check(ctx, resp.observation, action)
    assert con.allow_action
    assert not any("protected_file" in reason for reason in con.reasons)


def test_visible_protected_file_detected_when_visible_in_observation():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = env.tool_response()
    ctx = _context(env, resp)
    con = ConstraintMonitor().check(ctx, resp.observation, AgentAction("delete", "/workspace/tmp/protected.tmp"))
    assert not con.allow_action
    assert any("visible_protected_file" in reason for reason in con.reasons)


def test_composite_combines_reasons_and_deterministic():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    resp = FAULTS["compound_shift"]().apply(env.tool_response(), env, Random(1))
    ctx = _context(env, resp)
    action = AgentAction("delete", "/workspace/tmp/protected.tmp")
    a = CompositeMonitor().check(ctx, resp.observation, action)
    b = CompositeMonitor().check(ctx, resp.observation, action)
    assert a.to_dict() == b.to_dict()
    assert not a.allow_action
    assert a.reasons
