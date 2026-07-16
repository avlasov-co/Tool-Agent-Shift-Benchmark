"""Typed, normalized scientific identity schema version 19."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Mapping

from tool_agent_shift_benchmark.core.action_records import ACTION_RECORD_CONTRACT, EPISODE_RECORD_VERSION
from tool_agent_shift_benchmark.core.counterfactual import COUNTERFACTUAL_EVALUATION_CONTRACT
from tool_agent_shift_benchmark.core.monitoring import (
    MONITOR_COMPOSITION_CONTRACT,
    MonitorCompositionDescriptor,
    configured_monitor_composition,
    monitor_composition,
)
from tool_agent_shift_benchmark.core.oversight import (
    OVERSIGHT_TREATMENT_CONTRACT,
    OversightTreatmentDescriptor,
    oversight_treatment,
)
from tool_agent_shift_benchmark.core.policy_adapter import ENVIRONMENT_POLICY_ADAPTER_CONTRACT
from tool_agent_shift_benchmark.core.scenarios import (
    SCENARIO_FAMILY_CONTRACT,
    SCENARIO_MANIFEST_CONTRACT,
    SCENARIO_SPLIT_CONTRACT,
    ScenarioSplitDescriptor,
)
from tool_agent_shift_benchmark.core.seeding import SEED_STREAM_ALGORITHM, EpisodeSeedStreams
from tool_agent_shift_benchmark.core.serialization import register_dataclass, stable_hash
from tool_agent_shift_benchmark.core.shift_context import SHIFT_CONTEXT_SCHEMA_VERSION

if TYPE_CHECKING:
    from tool_agent_shift_benchmark.core.catalog import PluginCatalog
    from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec

IDENTITY_SCHEMA_VERSION = "19"
SCENARIO_GENERATOR_NAME = "deterministic_synthetic_scenarios"
SCENARIO_GENERATOR_VERSION = "3.0.0"
EVALUATOR_NAME = "hidden_state_evaluator"
EVALUATOR_VERSION = "2.0.0"
STEP_SEMANTICS_VERSION = "environment-state-machine-v2"


@dataclass(frozen=True)
class ComponentIdentity:
    kind: str
    name: str
    version: str
    contract_version: str
    implementation_identifier: str = "legacy_unspecified"
    configuration_hash: str = "legacy_unspecified"
    trust_level: str = "legacy_unspecified"
    capabilities: tuple[str, ...] = ()
    isolation_mode: str = "legacy_unspecified"


@dataclass(frozen=True)
class ResourceIdentity:
    name: str
    sha256: str


@dataclass(frozen=True)
class FaultScheduleIdentity:
    contract: str
    schedule_id: str
    components: tuple[ComponentIdentity, ...]
    configured_severity: float
    onset_step: int
    duration: int | None
    persistence: str
    recurrence: int | None
    per_step_severity: tuple[float, ...]

    @property
    def severity(self) -> float:
        """Compatibility alias for identity-v3 consumers."""

        return self.configured_severity

    @property
    def start_step(self) -> int:
        """Compatibility alias for identity-v3 consumers."""

        return self.onset_step

    @property
    def end_step(self) -> int | None:
        """Return the final step for non-recurring finite schedules."""

        if self.duration is None or self.recurrence is not None:
            return None
        return self.onset_step + self.duration - 1

    @property
    def cadence(self) -> str:
        """Compatibility alias for identity-v3 consumers."""

        return "each_step" if self.recurrence is None else f"every_{self.recurrence}_steps"


@dataclass(frozen=True)
class StepSemanticsIdentity:
    version: str
    environment_policy_adapter_contract: str
    shift_context_schema_version: str
    maximum_steps: int
    requery_contract: str
    policy_memory_contract: str
    schema_registry_contract: str
    clock_contract: str
    maximum_requeries_per_step: int
    termination_conditions: tuple[str, ...]


@dataclass(frozen=True)
class SeedStreamIdentity:
    algorithm: str
    root_seed: int
    scenario_generation: str
    agent_behavior: str
    fault_behavior: str
    oversight: str
    execution: str
    analysis: str


@dataclass(frozen=True)
class SemanticIdentity:
    identity_schema_version: str
    scenario_generator: ComponentIdentity
    scenario_schema_version: str
    scenario_manifest_contract: str
    scenario_family_contract: str
    scenario_split_contract: str
    scenario_split: str
    scenario_split_indices: tuple[int, ...]
    scenario_splits: tuple[ScenarioSplitDescriptor, ...]
    environments: tuple[ComponentIdentity, ...]
    agents: tuple[ComponentIdentity, ...]
    shift_chains: tuple[tuple[ComponentIdentity, ...], ...]
    configured_severities: tuple[float, ...]
    fault_schedules: tuple[FaultScheduleIdentity, ...]
    fault_effect_contract: str
    fault_channel_contract: str
    fault_composition_contract: str
    action_record_contract: str
    episode_record_version: str
    counterfactual_evaluation_contract: str
    oversight_contract: str
    oversight_modes: tuple[str, ...]
    oversight_treatments: tuple[OversightTreatmentDescriptor, ...]
    monitor: ComponentIdentity
    monitor_composition_contract: str
    monitor_modes: tuple[str, ...]
    monitor_compositions: tuple[MonitorCompositionDescriptor, ...]
    step_semantics: StepSemanticsIdentity
    scenario_seed_streams: SeedStreamIdentity
    policy_resources_and_hashes: tuple[ResourceIdentity, ...]
    evaluator: ComponentIdentity
    episodes_per_combo: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperationalIdentity:
    config_path: str
    working_directory: str
    output_path: str
    workers: int
    episode_ids: tuple[str, ...]
    scenario_indices: tuple[int, ...]
    selection_offset: int
    selection_limit: int | None
    partition_index: int | None
    partition_count: int | None
    replay_episode_ids: tuple[str, ...]
    resume_episode_ids: tuple[str, ...]
    logging: str
    artifact_policy: str
    progress_display: bool
    retry_attempts: int
    failure_policy: str
    execution_batch_size: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentIdentity:
    schema_version: str
    run_id: str
    config_digest: str
    legacy_run_id: str
    semantic: SemanticIdentity
    operational: OperationalIdentity

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlannedEpisodeIdentity:
    identity_schema_version: str
    run_id: str
    scenario_id: str
    scenario_seed: int
    scenario_pair_id: str
    scenario_manifest_hash: str
    seed_streams: EpisodeSeedStreams
    fault_schedule_ids: tuple[str, ...]
    episode_id: str
    environment: ComponentIdentity
    agent: ComponentIdentity
    shift_chain: tuple[ComponentIdentity, ...]
    monitor: ComponentIdentity
    evaluator: ComponentIdentity
    monitor_mode: str
    oversight_mode: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _component(catalog: PluginCatalog, kind: str, name: str) -> ComponentIdentity:
    descriptor = catalog.descriptor(kind, name)
    return ComponentIdentity(
        kind,
        descriptor.name,
        descriptor.version,
        descriptor.contract_version,
        descriptor.implementation_identifier,
        descriptor.configuration_hash,
        descriptor.trust_level.value,
        descriptor.capabilities,
        descriptor.isolation_mode,
    )


def _component_key(component: ComponentIdentity) -> tuple[Any, ...]:
    return (
        component.kind,
        component.name,
        component.version,
        component.contract_version,
        component.implementation_identifier,
        component.configuration_hash,
        component.trust_level,
        component.capabilities,
        component.isolation_mode,
    )


def _chain_key(chain: tuple[ComponentIdentity, ...]) -> tuple[tuple[Any, ...], ...]:
    return tuple(_component_key(component) for component in chain)


def _normalize_resources(value: Any) -> tuple[ResourceIdentity, ...]:
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise ValueError("policy_resources must be a string-keyed mapping of SHA-256 hashes")
    resources: list[ResourceIdentity] = []
    for name, digest in value.items():
        if not isinstance(name, str) or not name:
            raise ValueError("policy resource names must be non-empty strings")
        if not isinstance(digest, str):
            raise ValueError(f"policy resource {name!r} must be a SHA-256 string")
        normalized = digest.lower()
        if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError(f"policy resource {name!r} must use a 64-character SHA-256 hash")
        resources.append(ResourceIdentity(name, normalized))
    return tuple(sorted(resources, key=lambda resource: resource.name))


def _legacy_run_id(spec: ExperimentSpec) -> str:
    legacy_steps = int((spec.legacy_source_config or {}).get("episode_steps", 1))
    return stable_hash(
        {
            "config": spec.identity_config_v1(),
            "seed": spec.seed,
            "envs": spec.environments,
            "agents": spec.agents,
            "shifts": spec.shifts,
            "severities": spec.severities,
            "steps": legacy_steps,
            "scenario_indices": (),
            "episode_ids": (),
        },
        prefix="run",
    )


def build_experiment_identity(spec: ExperimentSpec, catalog: PluginCatalog) -> ExperimentIdentity:
    """Build a normalized identity document without executing selected plugins.

    Environment and agent matrix order and the order of distinct shift chains
    are execution-only, so those collections are sorted. Order inside a shift
    chain is preserved because shifts are composed non-commutatively.
    """

    environments = tuple(
        sorted((_component(catalog, "environment", name) for name in spec.environments), key=_component_key)
    )
    agents = tuple(sorted((_component(catalog, "agent", name) for name in spec.agents), key=_component_key))
    configured_shift_chains = tuple(
        sorted(
            (tuple(_component(catalog, "shift", name) for name in chain) for chain in spec.shift_chains),
            key=_chain_key,
        )
    )
    normal_chain = (_component(catalog, "shift", "normal"),)
    shift_chains = tuple(
        sorted(
            {configured_shift_chains[index] for index in range(len(configured_shift_chains))} | {normal_chain},
            key=_chain_key,
        )
    )
    severities = tuple(sorted(float(severity) for severity in spec.severities))
    from tool_agent_shift_benchmark.core.fault_channels import FAULT_CHANNEL_CONTRACT
    from tool_agent_shift_benchmark.core.fault_composition import FAULT_COMPOSITION_CONTRACT
    from tool_agent_shift_benchmark.core.fault_effects import FAULT_EFFECT_CONTRACT
    from tool_agent_shift_benchmark.core.fault_schedule import FAULT_SCHEDULE_CONTRACT, FaultSchedule
    from tool_agent_shift_benchmark.core.memory import POLICY_MEMORY_CONTRACT
    from tool_agent_shift_benchmark.core.requery import TOOL_REQUERY_CONTRACT
    from tool_agent_shift_benchmark.core.schema_registry import SCHEMA_REGISTRY_CONTRACT
    from tool_agent_shift_benchmark.core.timing import CAUSAL_LATENCY_CONTRACT

    configured_schedules = spec.fault_schedules
    if not configured_schedules:
        configured_schedules = tuple(
            FaultSchedule(
                tuple(component.name for component in chain),
                severity,
                0,
                None,
                "persistent",
                None,
                (0.0 if tuple(component.name for component in chain) == ("normal",) else severity,),
            )
            for chain in shift_chains
            for severity in severities
            if not (len(chain) == 1 and chain[0].name == "normal" and severity != 1.0)
        )
    if not any(schedule.components == ("normal",) for schedule in configured_schedules):
        configured_schedules = configured_schedules + (
            FaultSchedule(("normal",), 1.0, 0, None, "persistent", None, (0.0,)),
        )
    schedules = tuple(
        FaultScheduleIdentity(
            contract=FAULT_SCHEDULE_CONTRACT,
            schedule_id=schedule.schedule_id,
            components=tuple(_component(catalog, "shift", name) for name in schedule.components),
            configured_severity=schedule.configured_severity,
            onset_step=schedule.onset_step,
            duration=schedule.duration,
            persistence=schedule.persistence,
            recurrence=schedule.recurrence,
            per_step_severity=schedule.per_step_severity,
        )
        for schedule in sorted(configured_schedules, key=lambda item: item.schedule_id)
    )
    config = spec.config
    evaluator = _component(catalog, "evaluator", str(config.get("evaluator", EVALUATOR_NAME)))
    configured_evaluator_version = str(config.get("evaluator_version", evaluator.version))
    if configured_evaluator_version != evaluator.version:
        raise ValueError(
            "configured evaluator_version does not match the registered plugin descriptor: "
            f"expected {evaluator.version!r}, got {configured_evaluator_version!r}"
        )
    semantic = SemanticIdentity(
        identity_schema_version=IDENTITY_SCHEMA_VERSION,
        scenario_generator=ComponentIdentity(
            "scenario_generator",
            str(config.get("scenario_generator", SCENARIO_GENERATOR_NAME)),
            str(config.get("scenario_generator_version", SCENARIO_GENERATOR_VERSION)),
            "1",
        ),
        scenario_schema_version=str(config.get("scenario_schema_version", "v2")),
        scenario_manifest_contract=SCENARIO_MANIFEST_CONTRACT,
        scenario_family_contract=SCENARIO_FAMILY_CONTRACT,
        scenario_split_contract=SCENARIO_SPLIT_CONTRACT,
        scenario_split=str(config.get("scenario_split", "development")),
        scenario_split_indices=tuple(spec.semantic_scenario_indices or ()),
        scenario_splits=tuple(
            ScenarioSplitDescriptor.create(str(split["name"]), split["indices"])
            for split in config.get("scenario_splits", ())
        ),
        environments=environments,
        agents=agents,
        shift_chains=shift_chains,
        configured_severities=severities,
        fault_schedules=schedules,
        fault_effect_contract=FAULT_EFFECT_CONTRACT,
        fault_channel_contract=FAULT_CHANNEL_CONTRACT,
        fault_composition_contract=FAULT_COMPOSITION_CONTRACT,
        action_record_contract=ACTION_RECORD_CONTRACT,
        episode_record_version=EPISODE_RECORD_VERSION,
        counterfactual_evaluation_contract=COUNTERFACTUAL_EVALUATION_CONTRACT,
        oversight_contract=OVERSIGHT_TREATMENT_CONTRACT,
        oversight_modes=spec.oversight_modes,
        oversight_treatments=tuple(oversight_treatment(mode) for mode in spec.oversight_modes),
        monitor=_component(catalog, "monitor", spec.monitor),
        monitor_composition_contract=MONITOR_COMPOSITION_CONTRACT,
        monitor_modes=spec.monitor_modes,
        monitor_compositions=(
            tuple(monitor_composition(mode) for mode in spec.monitor_modes)
            if spec.monitor == "composite"
            else (configured_monitor_composition(spec.monitor),)
        ),
        step_semantics=StepSemanticsIdentity(
            STEP_SEMANTICS_VERSION,
            ENVIRONMENT_POLICY_ADAPTER_CONTRACT,
            SHIFT_CONTEXT_SCHEMA_VERSION,
            spec.episode_steps,
            TOOL_REQUERY_CONTRACT,
            POLICY_MEMORY_CONTRACT,
            SCHEMA_REGISTRY_CONTRACT,
            CAUSAL_LATENCY_CONTRACT,
            spec.requery_attempts,
            ("completed", "unsafe_action", "abstained", "budget_exhausted"),
        ),
        scenario_seed_streams=SeedStreamIdentity(
            SEED_STREAM_ALGORITHM,
            spec.seed,
            "scenario_generation",
            "agent_behavior",
            "fault_behavior",
            "oversight",
            "execution",
            "analysis",
        ),
        policy_resources_and_hashes=_normalize_resources(config.get("policy_resources")),
        evaluator=evaluator,
        episodes_per_combo=spec.episodes_per_combo,
    )
    semantic_payload = semantic.to_dict()
    operational = OperationalIdentity(
        config_path=str(config.get("_config_path", config.get("config_path", ""))),
        working_directory=str(config.get("_working_directory", config.get("working_directory", ""))),
        output_path=str(config.get("output_path", "results")),
        workers=spec.workers,
        episode_ids=tuple(sorted(spec.episode_ids)),
        scenario_indices=tuple(sorted(spec.scenario_indices)),
        selection_offset=spec.selection_offset,
        selection_limit=spec.selection_limit,
        partition_index=spec.partition_index,
        partition_count=spec.partition_count,
        replay_episode_ids=tuple(sorted(spec.replay_episode_ids)),
        resume_episode_ids=tuple(sorted(str(value) for value in config.get("resume_episode_ids", ()))),
        logging=str(config.get("logging", "standard")),
        artifact_policy=spec.artifact_policy,
        progress_display=bool(config.get("progress_display", True)),
        retry_attempts=spec.retry_attempts,
        failure_policy=spec.failure_policy,
        execution_batch_size=int(config.get("execution_batch_size", 1)),
    )
    return ExperimentIdentity(
        schema_version=IDENTITY_SCHEMA_VERSION,
        run_id=stable_hash(semantic_payload, prefix="run"),
        config_digest=stable_hash(semantic_payload, prefix="cfg"),
        legacy_run_id=_legacy_run_id(spec),
        semantic=semantic,
        operational=operational,
    )


for _serializable_dataclass in (
    ComponentIdentity,
    ResourceIdentity,
    FaultScheduleIdentity,
    StepSemanticsIdentity,
    SeedStreamIdentity,
    SemanticIdentity,
    OperationalIdentity,
    ExperimentIdentity,
    PlannedEpisodeIdentity,
):
    register_dataclass(_serializable_dataclass)
