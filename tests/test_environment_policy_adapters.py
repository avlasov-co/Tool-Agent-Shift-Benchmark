from __future__ import annotations

import inspect
from dataclasses import replace

from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.contracts import PluginDescriptor, TrustLevel
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.policy_adapter import ENVIRONMENT_POLICY_ADAPTER_CONTRACT
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.policy_adapters import FILE_ACTION_SCHEMA, FileOpsPolicyAdapter
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment


def test_first_party_environments_supply_safe_generic_policy_adapters() -> None:
    for environment_type in (FileOpsEnvironment, CalendarOpsEnvironment, RiskOpsEnvironment):
        environment = environment_type(seed=5, scenario_index=0)
        response = environment.tool_response()
        adapter = environment.policy_adapter(response.observation)
        context = ObservationContext.from_policy_adapter(
            adapter,
            response.observation,
            current_time=environment.current_time,
        )

        assert adapter.contract_version == ENVIRONMENT_POLICY_ADAPTER_CONTRACT
        assert adapter.environment_name == environment.name
        assert adapter.action_schema["action_types"]
        assert context.visible_candidates(response.observation)
        assert (
            context.recommended_action(response.observation.data).action_type in adapter.action_schema["action_types"]
        )
        assert not hasattr(adapter, "environment")
        assert not hasattr(adapter, "hidden_ground_truth")
        assert not hasattr(adapter, "execute")


def test_central_policy_context_has_no_environment_name_dispatch() -> None:
    source = inspect.getsource(ObservationContext)

    assert '== "file_ops"' not in source
    assert '== "calendar_ops"' not in source
    assert '== "risk_ops"' not in source


class SyntheticInventoryEnvironment(FileOpsEnvironment):
    name = "synthetic_inventory"
    version = "9.0.0"

    def reset(self, seed: int, scenario_index: int = 0) -> None:
        super().reset(seed, scenario_index)
        self.scenario_id = f"{self.name}_scenario_{scenario_index}"

    def policy_adapter(self, observation):
        return FileOpsPolicyAdapter(
            self.name,
            tuple(self.required_fields),
            dict(observation.constraints),
            self.public_task_description(),
            {**FILE_ACTION_SCHEMA, "synthetic_plugin": True},
        )

    def tool_response(self):
        response = super().tool_response()
        return replace(response, observation=replace(response.observation, env_name=self.name))


def test_new_plugin_environment_runs_without_central_dispatch_changes() -> None:
    catalog = PluginCatalog(include_external=False)
    catalog.register(
        PluginDescriptor.for_factory(
            "environment",
            SyntheticInventoryEnvironment.name,
            SyntheticInventoryEnvironment,
            version=SyntheticInventoryEnvironment.version,
        ),
        SyntheticInventoryEnvironment,
    )
    config = {
        "schema_version": 2,
        "environments": [SyntheticInventoryEnvironment.name],
        "agents": ["naive"],
        "faults": ["normal"],
        "episodes_per_combo": 1,
        "episode_steps": 1,
        "plugin_references": [
            {
                "kind": "environment",
                "name": SyntheticInventoryEnvironment.name,
                "version": SyntheticInventoryEnvironment.version,
                "contract_version": "2",
                "entry_point": "tests.test_environment_policy_adapters:SyntheticInventoryEnvironment",
            }
        ],
    }

    episode = RunCoordinator(ExperimentSpec.from_config(config, seed=17), catalog).run()[0]
    adapter_trace = episode.metadata["step_trace"][0]["policy_adapter"]

    assert episode.env_name == SyntheticInventoryEnvironment.name
    assert episode.decision.action.action_type == "inspect_files"
    assert adapter_trace["environment_name"] == SyntheticInventoryEnvironment.name
    assert adapter_trace["action_schema"]["synthetic_plugin"] is True


def test_restricted_plugin_environment_runs_through_remote_policy_adapter() -> None:
    descriptor = PluginDescriptor.for_factory(
        "environment",
        SyntheticInventoryEnvironment.name,
        SyntheticInventoryEnvironment,
        version=SyntheticInventoryEnvironment.version,
        trust_level=TrustLevel.EXTERNAL_RESTRICTED,
        metadata={
            "isolation": {
                "startup_timeout_seconds": 3.0,
                "call_timeout_seconds": 1.0,
                "output_limit_bytes": 100_000,
            }
        },
    )
    catalog = PluginCatalog(include_external=False)
    catalog.register(descriptor, SyntheticInventoryEnvironment)
    config = {
        "schema_version": 2,
        "environments": [SyntheticInventoryEnvironment.name],
        "agents": ["naive"],
        "faults": ["normal"],
        "episodes_per_combo": 1,
        "episode_steps": 1,
        "plugin_references": [
            {
                "kind": "environment",
                "name": SyntheticInventoryEnvironment.name,
                "version": SyntheticInventoryEnvironment.version,
                "contract_version": "2",
                "entry_point": descriptor.implementation_identifier,
            }
        ],
    }

    episode = RunCoordinator(ExperimentSpec.from_config(config, seed=19), catalog).run()[0]

    assert episode.env_name == SyntheticInventoryEnvironment.name
    assert episode.metadata["step_trace"][0]["policy_adapter"]["environment_name"] == episode.env_name
    environment_manifest = next(
        item
        for item in episode.metadata["plugin_isolation"]["components"]
        if item["component"]["kind"] == "environment"
    )
    assert environment_manifest["runtime"]["mode"] == "bounded_subprocess_v1"
