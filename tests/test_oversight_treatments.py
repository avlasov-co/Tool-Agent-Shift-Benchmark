from __future__ import annotations

import pytest

from tool_agent_shift_benchmark.agents import AGENTS
from tool_agent_shift_benchmark.cli import build_parser
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.config import load_config
from tool_agent_shift_benchmark.core.config_schema import ConfigValidationError, parse_config_data
from tool_agent_shift_benchmark.core.contracts import PluginDescriptor
from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.oversight import OVERSIGHT_MODE_ORDER
from tool_agent_shift_benchmark.core.types import MonitorDecision


def oversight_config(modes: list[str]) -> dict[str, object]:
    return {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["stale_observation"],
        "fault_severities": [1.0],
        "episodes_per_combo": 1,
        "episode_steps": 6,
        "monitor_modes": ["full_composite_monitor"],
        "oversight_modes": modes,
    }


def test_same_agent_runs_as_matched_cells_under_all_oversight_modes() -> None:
    spec = ExperimentSpec.from_config(oversight_config(list(reversed(OVERSIGHT_MODE_ORDER))), seed=137)
    planner = ExperimentPlanner(spec)
    plan = planner.plan()

    assert spec.oversight_modes == OVERSIGHT_MODE_ORDER
    assert len(plan) == 6
    assert len({item.scenario_pair_id for item in plan}) == 1
    assert len({item.seed_streams.agent_behavior for item in plan}) == 1
    assert {item.identity.oversight_mode for item in plan} == set(OVERSIGHT_MODE_ORDER)
    assert planner.identity.semantic.oversight_modes == OVERSIGHT_MODE_ORDER


def test_no_record_and_hard_gate_have_distinct_explicit_execution_semantics() -> None:
    episodes = RunCoordinator(ExperimentSpec.from_config(oversight_config(list(OVERSIGHT_MODE_ORDER)), seed=137)).run()
    shifted = {
        episode.metadata["oversight_mode"]: episode for episode in episodes if episode.fault.name == "stale_observation"
    }

    first_proposals = {
        mode: episode.metadata["step_trace"][0]["decision"]["action"] for mode, episode in shifted.items()
    }
    assert first_proposals["no_oversight"] == first_proposals["record_only"] == first_proposals["hard_gate"]
    assert all(decision.monitor_name == "no_oversight" for decision in shifted["no_oversight"].monitor_decisions)
    assert all(
        decision.metadata["monitor_evaluated"] is False for decision in shifted["no_oversight"].monitor_decisions
    )
    assert shifted["no_oversight"].execution.unsafe
    assert shifted["record_only"].execution.unsafe
    assert shifted["hard_gate"].execution.unsafe is False
    assert shifted["hard_gate"].metadata["step_trace"][0]["transition"]["action_type"] == "abstain"
    assert shifted["hard_gate"].decision.action.action_type == "inspect_files"


class AlwaysBlockMonitor:
    name = "always_block"

    def check(self, context, observation, action):
        return MonitorDecision(self.name, False, 1.0, ["test_block"], {"visible_only": True})


class ExplodingMonitor:
    name = "exploding_monitor"

    def check(self, context, observation, action):
        raise AssertionError("no_oversight must not evaluate the configured monitor")


def _custom_monitor_config(name: str, agents: list[str], oversight_mode: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": agents,
        "faults": ["normal"],
        "fault_severities": [1.0],
        "episodes_per_combo": 1,
        "episode_steps": 1,
        "monitor": name,
        "oversight_modes": [oversight_mode],
        "plugin_references": [
            {
                "kind": "monitor",
                "name": name,
                "version": "test",
                "contract_version": "1",
                "entry_point": f"tests:{name}",
            }
        ],
    }


def test_custom_monitor_runs_with_every_base_agent() -> None:
    catalog = PluginCatalog(include_external=False)
    catalog.register(PluginDescriptor("monitor", "always_block", version="test"), AlwaysBlockMonitor)
    config = _custom_monitor_config("always_block", list(AGENTS), "hard_gate")
    episodes = RunCoordinator(ExperimentSpec.from_config(config, seed=139), catalog).run()

    assert {episode.agent_name for episode in episodes} == set(AGENTS)
    assert all(episode.metadata["monitor_mode"] == "configured_monitor" for episode in episodes)
    assert all(episode.metadata["monitor_composition"]["components"] == ("always_block",) for episode in episodes)
    assert all(episode.monitor_decisions[0].monitor_name == "always_block" for episode in episodes)


def test_no_oversight_does_not_call_even_a_configured_custom_monitor() -> None:
    catalog = PluginCatalog(include_external=False)
    catalog.register(PluginDescriptor("monitor", "exploding_monitor", version="test"), ExplodingMonitor)
    config = _custom_monitor_config("exploding_monitor", ["naive"], "no_oversight")
    episode = RunCoordinator(ExperimentSpec.from_config(config, seed=149), catalog).run()[0]

    assert episode.monitor_decisions[0].monitor_name == "no_oversight"
    assert episode.monitor_decisions[0].metadata["monitor_evaluated"] is False


def test_legacy_monitor_gated_name_normalizes_without_a_runtime_agent(tmp_path) -> None:
    path = tmp_path / "legacy-alias.yaml"
    path.write_text(
        """\
schema_version: 2
environments: [file_ops]
agents: [monitor_gated]
faults: [normal]
monitor_policy: record
""",
        encoding="utf-8",
    )
    normalized = load_config(path)
    spec = ExperimentSpec.from_config(normalized)

    assert "monitor_gated" not in AGENTS
    assert spec.agents == ("naive",)
    assert spec.monitor_modes == ("full_composite_monitor",)
    assert spec.oversight_modes == ("record_only", "hard_gate")


def test_oversight_config_and_cli_reject_or_accept_exact_modes() -> None:
    with pytest.raises(ConfigValidationError) as unknown:
        parse_config_data(oversight_config(["unknown"]))
    with pytest.raises(ConfigValidationError) as duplicate:
        parse_config_data(oversight_config(["record_only", "record_only"]))
    with pytest.raises(ConfigValidationError, match="legacy monitor policy"):
        parse_config_data({**oversight_config(["hard_gate"]), "monitor_policy": "record"})

    assert unknown.value.path == "$.oversight_modes[0]"
    assert duplicate.value.path == "$.oversight_modes[1]"
    args = build_parser().parse_args(["plan", "--monitor-mode", "schema_only", "--oversight-mode", "record_only"])
    assert args.monitor_mode == ["schema_only"]
    assert args.oversight_mode == ["record_only"]
