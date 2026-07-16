"""Typed, normalized scientific identity schema version 2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Mapping

from tool_agent_shift_benchmark.core.serialization import register_dataclass, stable_hash

if TYPE_CHECKING:
    from tool_agent_shift_benchmark.core.catalog import PluginCatalog
    from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec

IDENTITY_SCHEMA_VERSION = "2"
SCENARIO_GENERATOR_NAME = "deterministic_synthetic_scenarios"
SCENARIO_GENERATOR_VERSION = "2.0.0"
EVALUATOR_NAME = "hidden_state_evaluator"
EVALUATOR_VERSION = "1.0.0"
SEED_STREAM_VERSION = "sha256-truncated-31-v1"
STEP_SEMANTICS_VERSION = "terminate-on-outcome-v1"


@dataclass(frozen=True)
class ComponentIdentity:
    kind: str
    name: str
    version: str
    contract_version: str


@dataclass(frozen=True)
class ResourceIdentity:
    name: str
    sha256: str


@dataclass(frozen=True)
class FaultScheduleIdentity:
    components: tuple[ComponentIdentity, ...]
    severity: float
    start_step: int
    end_step: int
    cadence: str


@dataclass(frozen=True)
class StepSemanticsIdentity:
    version: str
    maximum_steps: int
    termination_conditions: tuple[str, ...]


@dataclass(frozen=True)
class SeedStreamIdentity:
    version: str
    root_seed: int
    scenario_stream: str
    step_stream: str
    shift_stream: str


@dataclass(frozen=True)
class SemanticIdentity:
    identity_schema_version: str
    scenario_generator: ComponentIdentity
    scenario_schema_version: str
    scenario_split: str
    scenario_split_indices: tuple[int, ...]
    environments: tuple[ComponentIdentity, ...]
    agents: tuple[ComponentIdentity, ...]
    shift_chains: tuple[tuple[ComponentIdentity, ...], ...]
    configured_severities: tuple[float, ...]
    fault_schedules: tuple[FaultScheduleIdentity, ...]
    oversight_treatment: str
    monitor: ComponentIdentity
    monitor_modes: tuple[str, ...]
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
    scenario_pair_id: str | None
    episode_id: str
    environment: ComponentIdentity
    agent: ComponentIdentity
    shift_chain: tuple[ComponentIdentity, ...]
    monitor: ComponentIdentity
    evaluator: ComponentIdentity

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _component(catalog: PluginCatalog, kind: str, name: str) -> ComponentIdentity:
    descriptor = catalog.descriptor(kind, name)
    return ComponentIdentity(kind, descriptor.name, descriptor.version, descriptor.contract_version)


def _component_key(component: ComponentIdentity) -> tuple[str, str, str, str]:
    return component.kind, component.name, component.version, component.contract_version


def _chain_key(chain: tuple[ComponentIdentity, ...]) -> tuple[tuple[str, str, str, str], ...]:
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
    return stable_hash(
        {
            "config": spec.identity_config_v1(),
            "seed": spec.seed,
            "envs": spec.environments,
            "agents": spec.agents,
            "shifts": spec.shifts,
            "severities": spec.severities,
            "steps": spec.episode_steps,
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
    shift_chains = tuple(
        sorted(
            (tuple(_component(catalog, "shift", name) for name in chain) for chain in spec.shift_chains),
            key=_chain_key,
        )
    )
    severities = tuple(sorted(float(severity) for severity in spec.severities))
    schedules = tuple(
        FaultScheduleIdentity(chain, severity, 0, spec.episode_steps - 1, "each_step")
        for chain in shift_chains
        for severity in severities
        if not (len(chain) == 1 and chain[0].name == "normal" and severity != 1.0)
    )
    config = spec.config
    semantic = SemanticIdentity(
        identity_schema_version=IDENTITY_SCHEMA_VERSION,
        scenario_generator=ComponentIdentity(
            "scenario_generator",
            str(config.get("scenario_generator", SCENARIO_GENERATOR_NAME)),
            str(config.get("scenario_generator_version", SCENARIO_GENERATOR_VERSION)),
            "1",
        ),
        scenario_schema_version=str(config.get("scenario_schema_version", "v1")),
        scenario_split=str(config.get("scenario_split", "default")),
        scenario_split_indices=tuple(spec.semantic_scenario_indices or ()),
        environments=environments,
        agents=agents,
        shift_chains=shift_chains,
        configured_severities=severities,
        fault_schedules=schedules,
        oversight_treatment=spec.monitor_policy,
        monitor=_component(catalog, "monitor", spec.monitor),
        monitor_modes=tuple(sorted(str(mode) for mode in config.get("monitor_modes", ()))),
        step_semantics=StepSemanticsIdentity(
            STEP_SEMANTICS_VERSION,
            spec.episode_steps,
            ("unsafe_action", "abstained", "success", "max_steps"),
        ),
        scenario_seed_streams=SeedStreamIdentity(
            SEED_STREAM_VERSION,
            spec.seed,
            "scenario",
            "episode-step",
            "ordered-shift-component",
        ),
        policy_resources_and_hashes=_normalize_resources(config.get("policy_resources")),
        evaluator=ComponentIdentity(
            "evaluator",
            str(config.get("evaluator", EVALUATOR_NAME)),
            str(config.get("evaluator_version", EVALUATOR_VERSION)),
            "1",
        ),
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
