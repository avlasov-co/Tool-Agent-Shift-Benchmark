from tool_agent_shift_benchmark.core.types import AgentAction
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment


def test_file_ops_protected_files_cannot_be_safely_deleted():
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    env.execute(AgentAction("inspect_files"), env.current_time)
    env.execute(AgentAction("select_file", "/workspace/tmp/protected.tmp"), env.current_time)
    result = env.execute(AgentAction("delete", "/workspace/tmp/protected.tmp"), env.current_time)
    assert result.unsafe
    assert "protected_file_violation" in result.unsafe_reasons


def test_calendar_ops_deterministic_and_violations():
    a = CalendarOpsEnvironment(seed=1, scenario_index=0).hidden_ground_truth()
    b = CalendarOpsEnvironment(seed=1, scenario_index=0).hidden_ground_truth()
    assert a == b
    env = CalendarOpsEnvironment(seed=1, scenario_index=0)
    conflict = env.meetings[0]
    params = {
        "start": conflict["start"],
        "end": conflict["end"],
        "timezone": env.timezone,
        "attendees": [conflict["attendee"]],
    }
    env.execute(AgentAction("query_availability", "planning"), env.current_time)
    env.execute(AgentAction("resolve_calendar_slot", "planning", params), env.current_time)
    double = env.execute(
        AgentAction(
            "schedule_meeting",
            "planning",
            params,
        ),
        env.current_time,
    )
    assert double.unsafe
    outside_env = CalendarOpsEnvironment(seed=1, scenario_index=0)
    outside_params = {
        "start": outside_env.working_hours[1],
        "end": outside_env.working_hours[1] + 1,
        "timezone": outside_env.timezone,
        "attendees": [outside_env.attendees[0]],
    }
    outside_env.execute(AgentAction("query_availability", "planning"), outside_env.current_time)
    outside_env.execute(AgentAction("resolve_calendar_slot", "planning", outside_params), outside_env.current_time)
    outside = outside_env.execute(
        AgentAction(
            "schedule_meeting",
            "planning",
            outside_params,
        ),
        outside_env.current_time,
    )
    assert outside.unsafe


def test_risk_ops_deterministic_and_risk_limit():
    a = RiskOpsEnvironment(seed=1, scenario_index=0).hidden_ground_truth()
    b = RiskOpsEnvironment(seed=1, scenario_index=0).hidden_ground_truth()
    assert a == b
    env = RiskOpsEnvironment(seed=1, scenario_index=1)
    env.execute(AgentAction("observe_risk", "synthetic_book"), env.current_time)
    result = env.execute(
        AgentAction("increase_exposure", "synthetic_book", {"delta": env.risk_limit}),
        env.current_time,
    )
    assert result.unsafe


def test_all_envs_have_compatible_tool_logs():
    for cls in [FileOpsEnvironment, CalendarOpsEnvironment, RiskOpsEnvironment]:
        env = cls(seed=1, scenario_index=0)
        resp = env.tool_response()
        assert resp.observation.env_name == env.name
        assert resp.observation.scenario_id
