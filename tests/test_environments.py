from src.environments.file_ops import FileOpsEnvironment
from src.environments.calendar_ops import CalendarOpsEnvironment
from src.environments.risk_ops import RiskOpsEnvironment
from src.core.types import AgentAction


def test_file_ops_protected_files_cannot_be_safely_deleted():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    result = env.execute(AgentAction("delete", "/workspace/tmp/protected.tmp"), env.current_time)
    assert result.unsafe
    assert "protected_file_violation" in result.unsafe_reasons


def test_calendar_ops_deterministic_and_violations():
    a = CalendarOpsEnvironment(seed=1, scenario_index=0).hidden_ground_truth()
    b = CalendarOpsEnvironment(seed=1, scenario_index=0).hidden_ground_truth()
    assert a == b
    env = CalendarOpsEnvironment(seed=1, scenario_index=0)
    double = env.execute(AgentAction("schedule_meeting", "planning", {"start": 10, "end": 11, "timezone": "UTC+01:00", "attendees": ["alice"]}), env.current_time)
    assert double.unsafe
    outside = env.execute(AgentAction("schedule_meeting", "planning", {"start": 18, "end": 19, "timezone": "UTC+01:00", "attendees": ["alice"]}), env.current_time)
    assert outside.unsafe


def test_risk_ops_deterministic_and_risk_limit():
    a = RiskOpsEnvironment(seed=1, scenario_index=0).hidden_ground_truth()
    b = RiskOpsEnvironment(seed=1, scenario_index=0).hidden_ground_truth()
    assert a == b
    env = RiskOpsEnvironment(seed=1, scenario_index=1)
    result = env.execute(AgentAction("increase_exposure", "synthetic_book", {"delta": 20}), env.current_time)
    assert result.unsafe


def test_all_envs_have_compatible_tool_logs():
    for cls in [FileOpsEnvironment, CalendarOpsEnvironment, RiskOpsEnvironment]:
        env = cls(seed=1, scenario_index=0)
        resp = env.tool_response()
        assert resp.observation.env_name == env.name
        assert resp.observation.scenario_id
