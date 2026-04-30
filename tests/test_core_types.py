import json
import pytest
from src.core.types import AgentAction, AgentDecision, FaultConfig, Observation, ToolResponse, FailureCase, stable_hash
from src.core.episode import Episode
from src.core.types import ExecutionResult


def test_objects_serialize_and_required_fields():
    obs = Observation("file_ops", "s1", 1, {"files": []})
    tr = ToolResponse("tool", True, obs)
    action = AgentAction("abstain", abstain=True)
    decision = AgentDecision("agent", action, 0.5)
    d = decision.to_dict()
    assert d["agent_name"] == "agent"
    assert tr.to_dict()["observation"]["env_name"] == "file_ops"
    json.dumps(d)


def test_invalid_states_rejected():
    with pytest.raises(ValueError):
        Observation("", "s", 1, {})
    with pytest.raises(ValueError):
        AgentDecision("a", AgentAction("act"), 2.0)
    with pytest.raises(ValueError):
        FaultConfig("bad", severity=-1)


def test_episode_ids_stable_and_seed_preserved():
    obs = Observation("file_ops", "s1", 1, {"files": []})
    tr = ToolResponse("tool", True, obs)
    dec = AgentDecision("agent", AgentAction("abstain", abstain=True), 0.5)
    ex = ExecutionResult(False, False, False, False)
    ep1 = Episode("file_ops", "s1", "agent", FaultConfig("normal"), 42, "run", tr, dec, [], ex)
    ep2 = Episode("file_ops", "s1", "agent", FaultConfig("normal"), 42, "run", tr, dec, [], ex)
    assert ep1.episode_id == ep2.episode_id
    assert ep1.seed == 42


def test_failure_cases_link_episode_id():
    obs = Observation("file_ops", "s1", 1, {"files": []})
    tr = ToolResponse("tool", True, obs)
    dec = AgentDecision("agent", AgentAction("delete", "/x"), 0.5)
    ex = ExecutionResult(False, True, True, False, ["unsafe"])
    ep = Episode("file_ops", "s1", "agent", FaultConfig("normal"), 42, "run", tr, dec, [], ex)
    fc = ep.failure_case()
    assert fc.episode_id == ep.episode_id
    assert fc.case_id.startswith("case_")
