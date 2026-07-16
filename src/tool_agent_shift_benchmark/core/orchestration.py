"""Deterministic planning and episode orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any, Callable

from tool_agent_shift_benchmark.core.action_records import (
    ACTION_RECORD_CONTRACT,
    EPISODE_RECORD_VERSION,
    ActionRecord,
)
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.context import ObservationContext, redact_response_for_policy
from tool_agent_shift_benchmark.core.contracts import IdentityMismatchError, OrchestrationError, PluginDescriptor
from tool_agent_shift_benchmark.core.counterfactual import COUNTERFACTUAL_EVALUATION_CONTRACT
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.fault_composition import FAULT_COMPOSITION_CONTRACT, compose_fault_chain
from tool_agent_shift_benchmark.core.fault_effects import FAULT_EFFECT_CONTRACT
from tool_agent_shift_benchmark.core.fault_schedule import FaultSchedule
from tool_agent_shift_benchmark.core.identity import (
    ComponentIdentity,
    ExperimentIdentity,
    PlannedEpisodeIdentity,
    build_experiment_identity,
)
from tool_agent_shift_benchmark.core.isolation import ISOLATION_MANIFEST_CONTRACT, PluginIsolationError
from tool_agent_shift_benchmark.core.lifecycle import STEP_LIFECYCLE_CONTRACT, StateTransition
from tool_agent_shift_benchmark.core.memory import (
    POLICY_MEMORY_CONTRACT,
    MemoryCorruptionRequest,
    PolicyMemoryChannel,
)
from tool_agent_shift_benchmark.core.monitoring import (
    configured_monitor_composition,
    monitor_composition,
    resolve_monitor_modes,
)
from tool_agent_shift_benchmark.core.oversight import (
    OVERSIGHT_TREATMENT_CONTRACT,
    apply_oversight,
    oversight_treatment,
    resolve_oversight_modes,
)
from tool_agent_shift_benchmark.core.requery import (
    TOOL_CALL_COST_UNITS,
    TOOL_REQUERY_CONTRACT,
    ToolAttemptRecord,
)
from tool_agent_shift_benchmark.core.scenarios import (
    SCENARIO_FAMILY_CONTRACT,
    SCENARIO_MANIFEST_CONTRACT,
    SCENARIO_SPLIT_CONTRACT,
    ScenarioManifestError,
    ScenarioSpec,
    read_scenario_manifest,
    write_scenario_manifest,
)
from tool_agent_shift_benchmark.core.seeding import EpisodeSeedStreams, derive_seed, episode_seed_streams
from tool_agent_shift_benchmark.core.serialization import canonical_loads, write_json
from tool_agent_shift_benchmark.core.shift_context import SHIFT_CONTEXT_SCHEMA_VERSION, ShiftContext
from tool_agent_shift_benchmark.core.timing import CAUSAL_LATENCY_CONTRACT, ResponseTiming
from tool_agent_shift_benchmark.core.types import (
    AgentAction,
    AgentDecision,
    FaultConfig,
    MonitorDecision,
    ToolResponse,
    stable_hash,
)
from tool_agent_shift_benchmark.monitors.composite import CompositeMonitor

OPERATIONAL_SELECTOR_KEYS = frozenset(
    {
        "episode_ids",
        "scenario_indices",
        "selection_offset",
        "selection_limit",
        "partition_index",
        "partition_count",
        "replay_episode_ids",
        "resume_episode_ids",
    }
)
LEGACY_FORMAT_KEYS = frozenset({"schema_version", "migration", "fault_schedules", "scenario_splits"})


class UnknownEpisodeSelectionError(ValueError):
    """Raised when an ID selector does not refer to the canonical full plan."""

    def __init__(self, selection: str, episode_ids: set[str]):
        self.selection = selection
        self.episode_ids = tuple(sorted(episode_ids))
        super().__init__(f"unknown {selection} episode IDs: {', '.join(self.episode_ids)}")


@dataclass(frozen=True)
class ExperimentSpec:
    config: dict[str, Any]
    seed: int = 42
    environments: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    shifts: tuple[str, ...] = ()
    shift_chains: tuple[tuple[str, ...], ...] = ()
    severities: tuple[float, ...] = (1.0,)
    fault_schedules: tuple[FaultSchedule, ...] = ()
    episodes_per_combo: int = 1
    episode_steps: int = 6
    workers: int = 1
    oversight_modes: tuple[str, ...] = ("hard_gate",)
    failure_policy: str = "continue"
    retry_attempts: int = 0
    requery_attempts: int = 2
    monitor: str = "composite"
    monitor_modes: tuple[str, ...] = ("full_composite_monitor",)
    artifact_policy: str = "bundle"
    scenario_indices: tuple[int, ...] = ()
    episode_ids: tuple[str, ...] = ()
    selection_offset: int = 0
    selection_limit: int | None = None
    partition_index: int | None = None
    partition_count: int | None = None
    replay_episode_ids: tuple[str, ...] = ()
    scenario_manifest_path: str = ""
    semantic_scenario_indices: tuple[int, ...] | None = None
    legacy_source_config: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.workers <= 0:
            raise ValueError("workers must be positive")
        if self.retry_attempts < 0 or self.requery_attempts < 0:
            raise ValueError("retry and requery attempts must be non-negative")
        if any(index < 0 for index in self.scenario_indices):
            raise ValueError("scenario_indices must be non-negative")
        if self.selection_offset < 0:
            raise ValueError("selection_offset must be non-negative")
        if self.selection_limit is not None and self.selection_limit < 0:
            raise ValueError("selection_limit must be non-negative")
        if (self.partition_index is None) != (self.partition_count is None):
            raise ValueError("partition_index and partition_count must be provided together")
        if self.partition_count is not None and self.partition_count <= 0:
            raise ValueError("partition_count must be positive")
        if (
            self.partition_index is not None
            and self.partition_count is not None
            and not 0 <= self.partition_index < self.partition_count
        ):
            raise ValueError("partition_index must be between zero and partition_count - 1")
        if self.episode_ids and self.replay_episode_ids:
            raise ValueError("episode_ids and replay_episode_ids cannot be combined")

    @classmethod
    def from_config(cls, config: dict[str, Any], seed: int | None = None, **overrides: Any) -> "ExperimentSpec":
        from tool_agent_shift_benchmark.core.config_schema import parse_config_data

        internal = {key: value for key, value in config.items() if key.startswith("_")}
        public = {key: value for key, value in config.items() if not key.startswith("_")}
        config = {**parse_config_data(public).to_dict(), **internal}
        raw_shifts = tuple(str(x) for x in (config.get("faults") or ("normal",)))
        raw_chains = config.get("shift_chains")
        chains = (
            tuple(tuple(str(x) for x in chain) for chain in raw_chains)
            if raw_chains
            else tuple((x,) for x in raw_shifts)
        )
        selected_split = str(config.get("scenario_split", "development"))
        split_indices = next(
            (
                tuple(int(index) for index in split["indices"])
                for split in config.get("scenario_splits", [])
                if split["name"] == selected_split
            ),
            None,
        )
        worker_value = overrides.get("workers")
        scenario_index_values = overrides.get("scenario_indices")
        episode_id_values = overrides.get("episode_ids")
        offset_value = overrides.get("selection_offset")
        limit_value = overrides.get("selection_limit")
        partition_index_value = overrides.get("partition_index")
        partition_count_value = overrides.get("partition_count")
        replay_id_values = overrides.get("replay_episode_ids")
        return cls(
            config=dict(config),
            seed=int(config.get("seed", 42) if seed is None else seed),
            environments=tuple(overrides.get("environments") or config.get("environments") or ("file_ops",)),
            agents=tuple(overrides.get("agents") or config.get("agents") or ("naive",)),
            shifts=raw_shifts,
            shift_chains=chains,
            severities=tuple(float(x) for x in config.get("fault_severities", (1.0,))),
            fault_schedules=tuple(
                FaultSchedule.from_mapping(schedule) for schedule in config.get("fault_schedules", ())
            ),
            episodes_per_combo=int(config.get("episodes_per_combo", 3)),
            episode_steps=int(config.get("episode_steps", 6)),
            workers=int(config.get("workers", 1) if worker_value is None else worker_value),
            oversight_modes=resolve_oversight_modes(config.get("oversight_modes", ())),
            failure_policy=str(config.get("failure_policy", "continue")),
            retry_attempts=int(config.get("retry_attempts", 0)),
            requery_attempts=int(config.get("requery_attempts", 2)),
            monitor=str(config.get("monitor", "composite")),
            monitor_modes=(
                resolve_monitor_modes(config.get("monitor_modes", ()))
                if str(config.get("monitor", "composite")) == "composite"
                else ("configured_monitor",)
            ),
            artifact_policy=str(config.get("artifact_policy", "bundle")),
            scenario_indices=tuple(
                int(x)
                for x in (
                    config.get("scenario_indices", ()) if scenario_index_values is None else scenario_index_values
                )
            ),
            episode_ids=tuple(
                str(x) for x in (config.get("episode_ids", ()) if episode_id_values is None else episode_id_values)
            ),
            selection_offset=int(config.get("selection_offset", 0) if offset_value is None else offset_value),
            selection_limit=(
                int(value)
                if (value := config.get("selection_limit") if limit_value is None else limit_value) is not None
                else None
            ),
            partition_index=(
                int(value)
                if (value := config.get("partition_index") if partition_index_value is None else partition_index_value)
                is not None
                else None
            ),
            partition_count=(
                int(value)
                if (value := config.get("partition_count") if partition_count_value is None else partition_count_value)
                is not None
                else None
            ),
            replay_episode_ids=tuple(
                str(x) for x in (config.get("replay_episode_ids", ()) if replay_id_values is None else replay_id_values)
            ),
            scenario_manifest_path=str(config.get("scenario_manifest_path", "")),
            semantic_scenario_indices=split_indices,
            legacy_source_config=dict(public),
        )

    def identity_config_v1(self) -> dict[str, Any]:
        """Return the legacy hash input with operational selectors removed.

        Keeping the remaining shape unchanged preserves IDs from complete,
        unfiltered legacy plans while making all selection a post-ID operation.
        Identity v2 replaces this compatibility helper in Checkpoint 6.
        """

        excluded = OPERATIONAL_SELECTOR_KEYS | LEGACY_FORMAT_KEYS
        source = self.legacy_source_config or self.config
        return {key: value for key, value in source.items() if key not in excluded}

    def digest(self) -> str:
        return str(build_experiment_identity(self, PluginCatalog()).config_digest)


@dataclass(frozen=True)
class EpisodeSpec:
    identity: PlannedEpisodeIdentity
    environment: str
    agent: str
    shift: str
    severity: float
    scenario_index: int
    seed_streams: EpisodeSeedStreams
    fault_schedules: tuple[FaultSchedule, ...]
    scenario_spec: ScenarioSpec = dataclass_field(compare=False, hash=False, repr=False)

    @property
    def run_id(self) -> str:
        return str(self.identity.run_id)

    @property
    def scenario_id(self) -> str:
        return str(self.identity.scenario_id)

    @property
    def scenario_pair_id(self) -> str:
        return str(self.identity.scenario_pair_id)

    @property
    def seed(self) -> int:
        return int(self.identity.scenario_seed)

    @property
    def episode_id(self) -> str:
        return str(self.identity.episode_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "scenario_pair_id": self.scenario_pair_id,
            "episode_id": self.episode_id,
            "environment": self.environment,
            "agent": self.agent,
            "shift": self.shift,
            "severity": self.severity,
            "scenario_index": self.scenario_index,
            "seed": self.seed,
            "seed_streams": self.seed_streams.to_dict(),
            "fault_schedules": [schedule.to_dict() for schedule in self.fault_schedules],
            "monitor_mode": self.identity.monitor_mode,
            "oversight_mode": self.identity.oversight_mode,
            "scenario_manifest": self.scenario_spec.public_reference(),
            "identity": self.identity.to_dict(),
        }


def _component_identity(catalog: PluginCatalog, kind: str, name: str) -> ComponentIdentity:
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


class ExperimentPlanner:
    def __init__(self, spec: ExperimentSpec, catalog: PluginCatalog | None = None):
        self.spec, self.catalog = spec, catalog or PluginCatalog()
        shift_names = sorted({name for chain in spec.shift_chains for name in chain})
        self.catalog.validate(
            {
                "environment": list(spec.environments),
                "agent": list(spec.agents),
                "shift": shift_names,
                "monitor": [spec.monitor],
                "evaluator": [str(spec.config.get("evaluator", "hidden_state_evaluator"))],
            }
        )
        self.identity = build_experiment_identity(spec, self.catalog)
        self.run_id = self.identity.run_id
        self.legacy_run_id = self.identity.legacy_run_id
        self.config_digest = self.identity.config_digest
        self._scenario_specs: dict[tuple[str, int], ScenarioSpec] = {}

    def _materialize_scenario(
        self,
        environment: str,
        scenario_index: int,
        streams: EpisodeSeedStreams,
    ) -> ScenarioSpec:
        key = (environment, scenario_index)
        cached = self._scenario_specs.get(key)
        if cached is not None:
            if cached.scenario_seed != streams.scenario_generation:
                raise ScenarioManifestError(f"scenario seed changed while planning {key!r}")
            return cached
        scenario_id = f"{environment}_scenario_{scenario_index}"
        if self.spec.replay_episode_ids:
            if not self.spec.scenario_manifest_path:
                raise ScenarioManifestError("identity-v2 replay requires scenario_manifest_path")
            scenario = read_scenario_manifest(
                self.spec.scenario_manifest_path,
                scenario_id,
                scenario_seed=streams.scenario_generation,
            )
        else:
            environment_factory = self.catalog.get("environment", environment)
            environment_object = environment_factory(
                seed=streams.scenario_generation,
                scenario_index=scenario_index,
            )
            scenario = getattr(environment_object, "scenario_spec", None)
            if not isinstance(scenario, ScenarioSpec):
                raise ScenarioManifestError(f"environment {environment!r} did not produce a versioned ScenarioSpec")
            scenario = scenario.with_split(self.identity.semantic.scenario_split)
        if scenario.split != self.identity.semantic.scenario_split:
            raise ScenarioManifestError(
                "scenario manifest split mismatch: "
                f"expected {self.identity.semantic.scenario_split!r}, got {scenario.split!r}"
            )
        expected = (environment, scenario_id, scenario_index, streams.scenario_generation)
        actual = (
            scenario.environment,
            scenario.scenario_id,
            scenario.scenario_index,
            scenario.scenario_seed,
        )
        if actual != expected:
            raise ScenarioManifestError(f"scenario manifest identity mismatch: expected {expected!r}, got {actual!r}")
        self._scenario_specs[key] = scenario
        return scenario

    def scenario_specs(self) -> tuple[ScenarioSpec, ...]:
        return tuple(self._scenario_specs[key] for key in sorted(self._scenario_specs))

    def canonical_plan(self) -> list[EpisodeSpec]:
        """Construct every semantic episode before applying selectors."""

        planned: list[EpisodeSpec] = []
        treatments: list[tuple[tuple[str, ...], float]] = [(("normal",), 1.0)]
        seen_treatments: set[tuple[tuple[str, ...], float]] = {(("normal",), 1.0)}
        for chain in self.spec.shift_chains:
            for severity in self.spec.severities:
                treatment = (chain, float(severity))
                if chain == ("normal",) and severity != 1.0:
                    continue
                if treatment not in seen_treatments:
                    treatments.append(treatment)
                    seen_treatments.add(treatment)
        for env in self.spec.environments:
            scenario_indices = self.spec.semantic_scenario_indices or tuple(range(self.spec.episodes_per_combo))
            for index in scenario_indices:
                for agent in self.spec.agents:
                    for monitor_mode in self.spec.monitor_modes:
                        for oversight_mode in self.spec.oversight_modes:
                            for chain, severity in treatments:
                                planned.append(
                                    self._plan_treatment(
                                        env,
                                        index,
                                        agent,
                                        monitor_mode,
                                        oversight_mode,
                                        chain,
                                        severity,
                                    )
                                )
        return planned

    def _plan_treatment(
        self,
        env: str,
        index: int,
        agent: str,
        monitor_mode: str,
        oversight_mode: str,
        chain: tuple[str, ...],
        severity: float,
    ) -> EpisodeSpec:
        shift = "+".join(chain)
        scenario_id = f"{env}_scenario_{index}"
        generator = self.identity.semantic.scenario_generator
        streams = episode_seed_streams(
            root_seed=self.spec.seed,
            environment=env,
            scenario_index=index,
            generator_name=generator.name,
            generator_version=generator.version,
            scenario_schema_version=self.identity.semantic.scenario_schema_version,
            agent=agent,
            shift=shift,
            severity=severity,
            monitor=f"{self.spec.monitor}:{monitor_mode}",
            oversight_treatment=oversight_mode,
        )
        seed = streams.scenario_generation
        scenario = self._materialize_scenario(env, index, streams)
        schedules = tuple(
            schedule
            for schedule in self.spec.fault_schedules
            if schedule.components == chain and schedule.configured_severity == severity
        )
        if chain == ("normal",) and not schedules:
            schedules = (FaultSchedule(("normal",), 1.0, 0, None, "persistent", None, (0.0,)),)
        if not schedules:
            raise ValueError(f"missing fault schedule for treatment {chain!r} at severity {severity}")
        pair_id = stable_hash(
            {
                "contract": "scenario-pair-v1",
                "environment": env,
                "scenario_id": scenario_id,
                "scenario_manifest_hash": scenario.content_hash,
                "agent": agent,
                "agent_behavior_seed": streams.agent_behavior,
                "execution_seed": streams.execution,
            },
            prefix="pair",
        )
        episode_id = stable_hash(
            {
                "pair_id": pair_id,
                "fault": shift,
                "severity": severity,
                "fault_seed": streams.fault_behavior,
                "fault_schedules": [schedule.to_dict() for schedule in schedules],
                "monitor_mode": monitor_mode,
                "oversight_mode": oversight_mode,
                "run_id": self.run_id,
            },
            prefix="ep",
        )
        planned_identity = PlannedEpisodeIdentity(
            identity_schema_version=self.identity.schema_version,
            run_id=self.run_id,
            scenario_id=scenario_id,
            scenario_seed=seed,
            scenario_pair_id=pair_id,
            scenario_manifest_hash=scenario.content_hash,
            seed_streams=streams,
            fault_schedule_ids=tuple(schedule.schedule_id for schedule in schedules),
            episode_id=episode_id,
            environment=_component_identity(self.catalog, "environment", env),
            agent=_component_identity(self.catalog, "agent", agent),
            shift_chain=tuple(_component_identity(self.catalog, "shift", name) for name in chain),
            monitor=self.identity.semantic.monitor,
            evaluator=self.identity.semantic.evaluator,
            monitor_mode=monitor_mode,
            oversight_mode=oversight_mode,
        )
        return EpisodeSpec(
            planned_identity,
            env,
            agent,
            shift,
            severity,
            index,
            streams,
            schedules,
            scenario,
        )

    def plan(self) -> list[EpisodeSpec]:
        """Apply operational selectors to an already-identified canonical plan."""

        canonical = self.canonical_plan()
        known_ids = {item.episode_id for item in canonical}
        selected_ids = self.spec.replay_episode_ids or self.spec.episode_ids
        selection_name = "replay" if self.spec.replay_episode_ids else "selected"
        unknown = set(selected_ids) - known_ids
        if unknown:
            raise UnknownEpisodeSelectionError(selection_name, unknown)

        selected = canonical
        if self.spec.scenario_indices:
            indices = set(self.spec.scenario_indices)
            selected = [item for item in selected if item.scenario_index in indices]
        if selected_ids:
            ids = set(selected_ids)
            selected = [item for item in selected if item.episode_id in ids]
        pair_order = list(dict.fromkeys(item.scenario_pair_id for item in selected))
        if self.spec.partition_count is not None:
            included_pairs = {
                pair_id
                for position, pair_id in enumerate(pair_order)
                if position % self.spec.partition_count == self.spec.partition_index
            }
            selected = [item for item in selected if item.scenario_pair_id in included_pairs]
            pair_order = [pair_id for pair_id in pair_order if pair_id in included_pairs]
        start = self.spec.selection_offset
        stop = None if self.spec.selection_limit is None else start + self.spec.selection_limit
        selected_pairs = set(pair_order[start:stop])
        return [item for item in selected if item.scenario_pair_id in selected_pairs]


class EpisodeRunner:
    def __init__(self, spec: ExperimentSpec, catalog: PluginCatalog | None = None):
        self.spec, self.catalog = spec, catalog or PluginCatalog()

    @staticmethod
    def _descriptor_dict(component: ComponentIdentity) -> dict[str, Any]:
        return {
            "kind": component.kind,
            "name": component.name,
            "version": component.version,
            "contract_version": component.contract_version,
            "implementation_identifier": component.implementation_identifier,
            "configuration_hash": component.configuration_hash,
            "trust_level": component.trust_level,
            "capabilities": list(component.capabilities),
            "isolation_mode": component.isolation_mode,
        }

    @classmethod
    def _isolation_record(cls, instance: object, component: ComponentIdentity) -> dict[str, Any]:
        runtime = getattr(instance, "isolation_manifest", None)
        if isinstance(runtime, Mapping):
            selected = {
                key: value
                for key, value in runtime.items()
                if key
                in {
                    "contract",
                    "mode",
                    "cwd_policy",
                    "environment_policy",
                    "network_policy",
                    "filesystem_policy",
                    "resource_limits",
                    "timeouts",
                    "output_limit_bytes",
                }
            }
        else:
            selected = {
                "contract": ISOLATION_MANIFEST_CONTRACT,
                "mode": component.isolation_mode,
                "enforcement": "trusted_in_process" if component.isolation_mode == "in_process" else "unavailable",
            }
        return {
            "component": cls._descriptor_dict(component),
            "runtime": selected,
        }

    def _mismatch(
        self,
        item: EpisodeSpec,
        *,
        field: str,
        expected: Any,
        actual: Any,
        phase: str,
        descriptor: ComponentIdentity,
    ) -> None:
        if expected != actual:
            raise IdentityMismatchError(
                field=field,
                expected=expected,
                actual=actual,
                phase=phase,
                plugin_descriptor=self._descriptor_dict(descriptor),
                episode_id=item.episode_id,
            )

    def _validate_runtime_descriptor(
        self,
        item: EpisodeSpec,
        instance: object,
        expected: ComponentIdentity,
        phase: str,
    ) -> None:
        raw = getattr(instance, "runtime_descriptor", None)
        raw = raw() if callable(raw) else raw
        if raw is None:
            actual = expected
        elif isinstance(raw, PluginDescriptor):
            actual = ComponentIdentity(
                raw.kind,
                raw.name,
                raw.version,
                raw.contract_version,
                raw.implementation_identifier,
                raw.configuration_hash,
                raw.trust_level.value,
                raw.capabilities,
                raw.isolation_mode,
            )
        elif isinstance(raw, dict):
            try:
                actual = ComponentIdentity(
                    str(raw["kind"]),
                    str(raw["name"]),
                    str(raw["version"]),
                    str(raw["contract_version"]),
                    str(raw.get("implementation_identifier", "legacy_unspecified")),
                    str(raw.get("configuration_hash", "legacy_unspecified")),
                    str(raw.get("trust_level", "legacy_unspecified")),
                    tuple(str(value) for value in raw.get("capabilities", ())),
                    str(raw.get("isolation_mode", "legacy_unspecified")),
                )
            except KeyError as exc:
                raise IdentityMismatchError(
                    field="plugin_descriptor",
                    expected=self._descriptor_dict(expected),
                    actual=raw,
                    phase=phase,
                    plugin_descriptor=self._descriptor_dict(expected),
                    episode_id=item.episode_id,
                ) from exc
        else:
            actual = raw
        self._mismatch(
            item,
            field="plugin_descriptor",
            expected=self._descriptor_dict(expected),
            actual=self._descriptor_dict(actual) if isinstance(actual, ComponentIdentity) else actual,
            phase=phase,
            descriptor=expected,
        )

    def _validate_observation_identity(
        self,
        item: EpisodeSpec,
        env_name: str,
        scenario_id: str,
        phase: str,
    ) -> None:
        descriptor = item.identity.environment
        self._mismatch(
            item,
            field="observation.env_name",
            expected=item.environment,
            actual=env_name,
            phase=phase,
            descriptor=descriptor,
        )
        self._mismatch(
            item,
            field="observation.scenario_id",
            expected=item.scenario_id,
            actual=scenario_id,
            phase=phase,
            descriptor=descriptor,
        )

    def _observe_through_schedule(
        self,
        item: EpisodeSpec,
        env_obj: Any,
        *,
        step: int,
        attempt_number: int,
        maximum_attempts: int,
    ) -> tuple[
        ToolResponse,
        ToolResponse,
        list[dict[str, Any]],
        dict[str, Any],
        tuple[MemoryCorruptionRequest, ...],
    ]:
        clean = env_obj.tool_response()
        self._validate_observation_identity(
            item,
            clean.observation.env_name,
            clean.observation.scenario_id,
            "environment_response",
        )
        shifted = clean
        schedule_provenance: list[dict[str, Any]] = []
        fault_compositions: list[dict[str, Any]] = []
        memory_requests: list[MemoryCorruptionRequest] = []
        for schedule in item.fault_schedules:
            component_channels = []
            for component_name in schedule.components:
                component_factory = self.catalog.get("shift", component_name)
                descriptor_factory = getattr(component_factory, "channel_descriptor", None)
                if callable(descriptor_factory):
                    component_channels.append(descriptor_factory().to_dict())
            provenance = {
                **schedule.provenance(step),
                "attempt_number": attempt_number,
                "component_channels": component_channels,
                "shift_context_schema_version": SHIFT_CONTEXT_SCHEMA_VERSION,
            }
            schedule_provenance.append(provenance)
            scheduled_severity = schedule.severity_at(step)
            if scheduled_severity is None:
                continue
            applications: list[tuple[str, Any, int]] = []
            occurrences: dict[str, int] = {}
            for name in schedule.components:
                occurrence = occurrences.get(name, 0)
                occurrences[name] = occurrence + 1
                shift_rng_seed = derive_seed(
                    item.seed_streams.root_seed,
                    "fault_behavior",
                    {
                        "scenario_generation": item.seed_streams.scenario_generation,
                        "environment": item.environment,
                        "scenario_index": item.scenario_index,
                        "agent": item.agent,
                        "component": name,
                        "component_occurrence": occurrence,
                        "configured_severity": schedule.configured_severity,
                        "onset_step": schedule.onset_step,
                        "duration": schedule.duration,
                        "persistence": schedule.persistence,
                        "recurrence": schedule.recurrence,
                        "per_step_severity": schedule.per_step_severity,
                        "step": step,
                        "attempt_number": attempt_number,
                    },
                )
                shift_obj = self.catalog.get("shift", name)(severity=scheduled_severity)
                applications.append((name, shift_obj, shift_rng_seed))
                if getattr(shift_obj, "channel", "tool_response") == "policy_memory":
                    memory_requests.append(
                        MemoryCorruptionRequest(schedule.schedule_id, scheduled_severity, shift_rng_seed)
                    )
            lifecycle = shifted.observation.data.get("lifecycle")
            lifecycle_phase = str(lifecycle.get("phase", "unknown")) if isinstance(lifecycle, Mapping) else "unknown"
            policy_adapter = env_obj.policy_adapter(shifted.observation)
            shift_context = ShiftContext.create(
                step_index=step,
                attempt_number=attempt_number,
                public_scenario_metadata=item.scenario_spec.public_task_description,
                visible_schema={
                    "tool_name": shifted.tool_name,
                    "observation_schema_version": shifted.observation.schema_version,
                    "top_level_fields": sorted(shifted.observation.data),
                    "required_fields": policy_adapter.required_fields,
                    "action_schema": policy_adapter.action_schema,
                },
                timing={
                    "clock_unit": "ms",
                    "environment_time": int(getattr(env_obj, "current_time", shifted.observation.timestamp)),
                    "observation_timestamp": shifted.observation.timestamp,
                    "declared_latency_ms": shifted.latency_ms,
                },
                rng_seed=0,
                fault_schedule=provenance,
                channel_metadata={
                    "lifecycle_phase": lifecycle_phase,
                    "visible_constraints_reference_hash": stable_hash(
                        shifted.observation.constraints,
                        prefix="constraint_reference",
                    ),
                    "policy_adapter_contract": policy_adapter.contract_version,
                },
            )
            shifted, composition = compose_fault_chain(
                shifted,
                shift_context,
                applications,
                schedule_id=schedule.schedule_id,
                scheduled_severity=scheduled_severity,
            )
            fault_compositions.append(composition.to_dict())
            self._validate_observation_identity(
                item,
                shifted.observation.env_name,
                shifted.observation.scenario_id,
                "shift_response",
            )
        shifted_observation_metadata = dict(shifted.observation.metadata)
        shifted_observation_metadata["fault_schedule_provenance"] = schedule_provenance
        shifted = replace(
            shifted,
            observation=replace(shifted.observation, metadata=shifted_observation_metadata),
        )
        environment_clock_before = int(getattr(env_obj, "current_time", shifted.observation.timestamp))
        advance_time = getattr(env_obj, "advance_time_ms", None)
        if callable(advance_time):
            advance_time(shifted.latency_ms)
        elif shifted.latency_ms:
            raise RuntimeError("environment does not support causal latency clock advancement")
        response_received_at = int(getattr(env_obj, "current_time", environment_clock_before))
        timing = ResponseTiming(
            contract=CAUSAL_LATENCY_CONTRACT,
            clock_unit="ms",
            observation_timestamp=shifted.observation.timestamp,
            response_latency_ms=shifted.latency_ms,
            environment_clock_before=environment_clock_before,
            response_received_at=response_received_at,
        )
        shifted = replace(shifted, metadata={**shifted.metadata, "timing": timing.to_dict()})
        policy_response = redact_response_for_policy(shifted)
        visible_response_hash = stable_hash(policy_response.to_dict(), prefix="visible")
        tool_call_id = stable_hash(
            {
                "contract": TOOL_REQUERY_CONTRACT,
                "episode_id": item.episode_id,
                "step": step,
                "attempt_number": attempt_number,
            },
            prefix="call",
        )
        policy_requery_metadata = {
            "contract": TOOL_REQUERY_CONTRACT,
            "tool_call_id": tool_call_id,
            "attempt_number": attempt_number,
            "maximum_attempts": maximum_attempts,
            "remaining_requeries": maximum_attempts - attempt_number,
            "visible_response_hash": visible_response_hash,
        }
        policy_response = replace(
            policy_response,
            metadata={**policy_response.metadata, "requery": policy_requery_metadata},
        )
        shifted = replace(shifted, metadata={**shifted.metadata, "requery": policy_requery_metadata})
        response_provenance = {
            "source": "scheduled_shift_channel",
            "tool_call_id": tool_call_id,
            "visible_response_hash": visible_response_hash,
            "schedule_evaluations": schedule_provenance,
            "fault_compositions": fault_compositions,
            "realized_faults": shifted.observation.metadata.get("faults", []),
            "timing": timing.to_dict(),
            "clean_response_exposed": False,
        }
        return shifted, policy_response, schedule_provenance, response_provenance, tuple(memory_requests)

    def run(self, item: EpisodeSpec) -> Episode:
        env_obj = self.catalog.get("environment", item.environment)(
            seed=item.seed,
            scenario_index=item.scenario_index,
            scenario_spec=item.scenario_spec,
        )
        agent_obj = self.catalog.get("agent", item.agent)()
        setattr(agent_obj, "behavior_seed", item.seed_streams.agent_behavior)
        shift_names = tuple(
            dict.fromkeys(component for schedule in item.fault_schedules for component in schedule.components)
        )
        shift_objs = {name: self.catalog.get("shift", name)(severity=item.severity) for name in shift_names}
        evaluator = self.catalog.get(
            "evaluator",
            str(self.spec.config.get("evaluator", "hidden_state_evaluator")),
        )()
        memory_channel = PolicyMemoryChannel()
        stateful_memory = bool(getattr(agent_obj, "stateful_memory", False))
        monitor_factory = self.catalog.get("monitor", self.spec.monitor)
        monitor = (
            monitor_factory() if self.spec.monitor != "composite" else CompositeMonitor(mode=item.identity.monitor_mode)
        )
        self._validate_runtime_descriptor(item, env_obj, item.identity.environment, "environment_descriptor")
        self._validate_runtime_descriptor(item, agent_obj, item.identity.agent, "agent_descriptor")
        descriptors = {descriptor.name: descriptor for descriptor in item.identity.shift_chain}
        for name, shift_obj in shift_objs.items():
            self._validate_runtime_descriptor(item, shift_obj, descriptors[name], "shift_descriptor")
        self._validate_runtime_descriptor(item, monitor, item.identity.monitor, "monitor_descriptor")
        self._validate_runtime_descriptor(item, evaluator, item.identity.evaluator, "evaluator_descriptor")
        self._mismatch(
            item,
            field="environment.name",
            expected=item.environment,
            actual=getattr(env_obj, "name", None),
            phase="environment_identity",
            descriptor=item.identity.environment,
        )
        self._mismatch(
            item,
            field="environment.scenario_id",
            expected=item.scenario_id,
            actual=getattr(env_obj, "scenario_id", None),
            phase="environment_identity",
            descriptor=item.identity.environment,
        )
        self._mismatch(
            item,
            field="environment.seed",
            expected=item.seed,
            actual=getattr(env_obj, "seed", None),
            phase="environment_identity",
            descriptor=item.identity.environment,
        )
        self._mismatch(
            item,
            field="environment.scenario_index",
            expected=item.scenario_index,
            actual=getattr(env_obj, "scenario_index", None),
            phase="environment_identity",
            descriptor=item.identity.environment,
        )
        monitors: list[MonitorDecision] = []
        action_records: list[ActionRecord] = []
        step_trace: list[dict[str, Any]] = []
        evaluator_trace: list[dict[str, Any]] = []
        final_response = final_decision = final_execution = None
        stop_reason, failure_step, unsafe_steps = "budget_exhausted", "", 0
        state_transitions: list[dict[str, Any]] = []
        total_tool_calls = 0
        total_requeries = 0
        total_tool_cost_units = 0
        for step in range(self.spec.episode_steps):
            maximum_attempts = self.spec.requery_attempts + 1
            policy_attempts: list[dict[str, Any]] = []
            evaluator_attempts: list[dict[str, Any]] = []
            for attempt_number in range(1, maximum_attempts + 1):
                (
                    shifted,
                    policy_response,
                    schedule_provenance,
                    response_provenance,
                    memory_requests,
                ) = self._observe_through_schedule(
                    item,
                    env_obj,
                    step=step,
                    attempt_number=attempt_number,
                    maximum_attempts=maximum_attempts,
                )
                total_tool_calls += 1
                total_tool_cost_units += TOOL_CALL_COST_UNITS
                memory_read = memory_channel.read(
                    step=step,
                    stateful_agent=stateful_memory,
                    requests=memory_requests,
                )
                policy_adapter = env_obj.policy_adapter(policy_response.observation)
                context = ObservationContext.from_policy_adapter(
                    policy_adapter,
                    policy_response.observation,
                    current_time=int(policy_response.metadata["timing"]["response_received_at"]),
                    response_latency_ms=policy_response.latency_ms,
                    response_received_at=int(policy_response.metadata["timing"]["response_received_at"]),
                    memory=memory_read.policy_view,
                )
                decision = agent_obj.decide(context, policy_response)
                self._mismatch(
                    item,
                    field="decision.agent_name",
                    expected=item.agent,
                    actual=decision.agent_name,
                    phase="agent_decision",
                    descriptor=item.identity.agent,
                )
                memory_write_receipts = memory_channel.write(decision.memory_writes, step=step)
                response_provenance["memory"] = {
                    **memory_read.evaluator_dict(),
                    "writes": [entry.to_dict() for entry in memory_write_receipts],
                    "operations": [operation.to_dict() for operation in decision.memory_operations],
                }
                requery_requested = decision.action.is_requery
                can_requery = attempt_number < maximum_attempts
                outcome = (
                    "requery_requested"
                    if requery_requested and can_requery
                    else "requery_budget_exhausted"
                    if requery_requested
                    else "environment_action"
                )
                reason = decision.action.reason or ",".join(decision.reasons) or outcome
                attempt_record = ToolAttemptRecord(
                    contract=TOOL_REQUERY_CONTRACT,
                    step=step,
                    attempt_number=attempt_number,
                    maximum_attempts=maximum_attempts,
                    tool_call_id=str(policy_response.metadata["requery"]["tool_call_id"]),
                    decision_type=decision.action.action_type,
                    outcome=outcome,
                    reason=reason,
                    reasons=tuple(decision.reasons),
                    tool_cost_units=TOOL_CALL_COST_UNITS,
                    latency_ms=policy_response.latency_ms,
                    visible_response_hash=str(policy_response.metadata["requery"]["visible_response_hash"]),
                    response_provenance=response_provenance,
                )
                policy_attempts.append(
                    {
                        **attempt_record.policy_dict(),
                        "memory": memory_read.policy_dict(),
                        "memory_writes": [entry.to_dict() for entry in memory_write_receipts],
                        "memory_operations": [operation.to_dict() for operation in decision.memory_operations],
                    }
                )
                evaluator_attempts.append(attempt_record.to_dict())
                if requery_requested and can_requery:
                    total_requeries += 1
                    continue
                if requery_requested:
                    decision = AgentDecision(
                        decision.agent_name,
                        AgentAction("abstain", abstain=True, reason="requery_budget_exhausted"),
                        decision.confidence,
                        [*decision.reasons, "requery_budget_exhausted"],
                        {**decision.metadata, "runner_enforced_requery_budget": True},
                    )
                break
            monitor_decision, action = apply_oversight(
                item.identity.oversight_mode,
                monitor,
                context,
                policy_response.observation,
                decision.action,
            )
            monitors.append(monitor_decision)
            proposed_score = evaluator.score_action(
                env_obj,
                decision.action,
                observed_timestamp=policy_response.observation.timestamp,
            )
            executed_score = evaluator.score_action(
                env_obj,
                action,
                observed_timestamp=policy_response.observation.timestamp,
            )
            state_before = env_obj.lifecycle_snapshot()
            execution = env_obj.execute(action, observed_timestamp=policy_response.observation.timestamp)
            state_after = env_obj.lifecycle_snapshot()
            status = env_obj.lifecycle_status()
            if execution.unsafe:
                unsafe_steps += 1
                failure_step = failure_step or str(step)
            if status["terminal"]:
                stop_reason = str(status["stop_reason"])
            transition = StateTransition(
                contract=STEP_LIFECYCLE_CONTRACT,
                sequence=step,
                from_phase=str(state_before["phase"]),
                action_type=action.action_type,
                action_target=action.target,
                to_phase=str(state_after["phase"]),
                state_revision_before=int(state_before["state_revision"]),
                state_revision_after=int(state_after["state_revision"]),
                observation_timestamp=policy_response.observation.timestamp,
                execution_timestamp=int(state_after["current_time"]),
                transition_completed=bool(execution.metadata.get("transition_completed", execution.success)),
                terminal=bool(status["terminal"]),
                stop_reason=str(status["stop_reason"]),
                unsafe=execution.unsafe,
                unsafe_reasons=tuple(execution.unsafe_reasons),
                consequence=dict(execution.metadata),
            )
            intervention_score = evaluator.score_intervention(
                sequence=step,
                proposed=proposed_score,
                executed=executed_score,
                executed_action=action,
                monitor=monitor_decision,
                execution=execution,
            )
            score = {
                **evaluator.score(env_obj, action, execution),
                "counterfactual": intervention_score.to_dict(),
            }
            action_record = ActionRecord.complete(
                sequence=step,
                decision=decision,
                monitor=monitor_decision,
                oversight_mode=item.identity.oversight_mode,
                executed_action=action,
                execution=execution,
                stop_reason=str(status["stop_reason"] or "in_progress"),
                evaluator_labels=score,
            )
            action_records.append(action_record)
            state_transitions.append(transition.to_dict())
            policy_transition = {
                key: value
                for key, value in transition.to_dict().items()
                if key not in {"unsafe", "unsafe_reasons", "consequence"}
            }
            step_trace.append(
                {
                    "step": step,
                    "tool_response": policy_response.to_dict(),
                    "policy_adapter": policy_adapter.to_dict(),
                    "decision": decision.to_dict(),
                    "monitor": monitor_decision.to_dict(),
                    "action_record": action_record.policy_dict(),
                    "transition": policy_transition,
                    "attempt_count": len(policy_attempts),
                    "attempts": policy_attempts,
                    "observation_timestamp": policy_response.observation.timestamp,
                    "response_latency_ms": policy_response.latency_ms,
                    "execution_timestamp": int(state_after["current_time"]),
                    "environment_clock": int(env_obj.current_time),
                    "memory": memory_read.policy_dict(),
                    "memory_writes": [entry.to_dict() for entry in memory_write_receipts],
                    "memory_operations": [operation.to_dict() for operation in decision.memory_operations],
                }
            )
            evaluator_trace.append(
                {
                    "step": step,
                    "shift_provenance": shifted.observation.metadata.get("faults", []),
                    "fault_schedule_provenance": schedule_provenance,
                    "tool_attempts": evaluator_attempts,
                    "action_record": action_record.to_dict(),
                    **score,
                }
            )
            final_response, final_decision, final_execution = (
                shifted,
                decision,
                execution,
            )
            if status["terminal"]:
                break
        final_status = env_obj.lifecycle_status()
        if not final_status["terminal"]:
            env_obj.mark_budget_exhausted()
            final_status = env_obj.lifecycle_status()
            stop_reason = str(final_status["stop_reason"])
            if action_records and action_records[-1].stop_reason == "in_progress":
                action_records[-1] = replace(action_records[-1], stop_reason=stop_reason)
                evaluator_trace[-1]["action_record"] = action_records[-1].to_dict()
                step_trace[-1]["action_record"] = action_records[-1].policy_dict()
        intermediate_failure_count = sum(
            not transition["transition_completed"] and not transition["terminal"] for transition in state_transitions
        )
        recovered = bool(
            (
                item.shift != "normal"
                and final_execution
                and not final_execution.unsafe
                and final_decision is not None
                and (final_decision.action.abstain or any(not m.allow_action for m in monitors))
            )
            or (intermediate_failure_count and final_status["stop_reason"] == "completed")
        )
        fault_effects = [
            effect
            for step_entry in evaluator_trace
            for attempt in step_entry["tool_attempts"]
            for effect in attempt["response_provenance"]["realized_faults"]
        ]
        maximum_realized_effect = max(
            (float(effect.get("realized_magnitude", 0.0)) for effect in fault_effects),
            default=0.0,
        )
        metadata = {
            "config_path": self.spec.config.get("_config_path", ""),
            "combo_seed": item.seed,
            "seed_streams": item.seed_streams.to_dict(),
            "scenario_generator": self.identity_generator_metadata(item),
            "scenario_manifest": item.scenario_spec.public_reference(),
            "agent_initialization": {
                "behavior_seed": item.seed_streams.agent_behavior,
                "shared_across_treatments": True,
            },
            "fault_schedules": [schedule.to_dict() for schedule in item.fault_schedules],
            "fault_effect_contract": FAULT_EFFECT_CONTRACT,
            "fault_composition_contract": FAULT_COMPOSITION_CONTRACT,
            "action_record_contract": ACTION_RECORD_CONTRACT,
            "episode_record_version": EPISODE_RECORD_VERSION,
            "counterfactual_evaluation_contract": COUNTERFACTUAL_EVALUATION_CONTRACT,
            "monitor_mode": item.identity.monitor_mode,
            "plugin_isolation": {
                "contract": ISOLATION_MANIFEST_CONTRACT,
                "components": [
                    self._isolation_record(env_obj, item.identity.environment),
                    self._isolation_record(agent_obj, item.identity.agent),
                    *(self._isolation_record(shift_objs[name], descriptors[name]) for name in sorted(shift_objs)),
                    self._isolation_record(monitor, item.identity.monitor),
                    self._isolation_record(evaluator, item.identity.evaluator),
                ],
            },
            "monitor_composition": (
                monitor_composition(item.identity.monitor_mode)
                if self.spec.monitor == "composite"
                else configured_monitor_composition(self.spec.monitor)
            ).to_dict(),
            "oversight_contract": OVERSIGHT_TREATMENT_CONTRACT,
            "oversight_mode": item.identity.oversight_mode,
            "oversight_treatment": oversight_treatment(item.identity.oversight_mode).to_dict(),
            "configured_fault_severity": item.severity,
            "fault_effects": fault_effects,
            "fault_effect_applications": len(fault_effects),
            "maximum_realized_effect_magnitude": maximum_realized_effect,
            "requery_contract": TOOL_REQUERY_CONTRACT,
            "policy_memory_contract": POLICY_MEMORY_CONTRACT,
            "stateful_policy_memory": stateful_memory,
            "final_memory_reference_hash": memory_channel.pristine_reference_hash(),
            "causal_latency_contract": CAUSAL_LATENCY_CONTRACT,
            "maximum_requeries_per_step": self.spec.requery_attempts,
            "total_tool_calls": total_tool_calls,
            "total_requeries": total_requeries,
            "total_tool_cost_units": total_tool_cost_units,
            "episode_steps": self.spec.episode_steps,
            "steps_taken": len(step_trace),
            "multi_step": len(step_trace) > 1,
            "unsafe_step_count": unsafe_steps,
            "failure_step": failure_step,
            "stop_reason": stop_reason,
            "step_trace": step_trace,
            "state_transitions": state_transitions,
            "final_lifecycle_status": final_status,
            "evaluator_trace": evaluator_trace,
            "recovered": recovered,
            "intermediate_failure_count": intermediate_failure_count,
        }
        episode = Episode(
            env_name=item.environment,
            scenario_id=item.scenario_id,
            agent_name=item.agent,
            fault=FaultConfig(
                item.shift,
                item.severity,
                {
                    "schedule_ids": [schedule.schedule_id for schedule in item.fault_schedules],
                    "effect_contract": FAULT_EFFECT_CONTRACT,
                    "maximum_realized_effect_magnitude": maximum_realized_effect,
                },
            ),
            seed=item.seed,
            run_id=item.run_id,
            episode_id=item.episode_id,
            tool_response=final_response,
            decision=final_decision,
            monitor_decisions=monitors,
            execution=final_execution,
            metadata=metadata,
            scenario_pair_id=item.scenario_pair_id,
            identity_schema_version=item.identity.identity_schema_version,
            planned_identity=item.identity.to_dict(),
            episode_record_version=EPISODE_RECORD_VERSION,
            action_records=action_records,
        )
        for field, expected, actual in (
            ("run_id", item.run_id, episode.run_id),
            ("scenario_id", item.scenario_id, episode.scenario_id),
            ("scenario_pair_id", item.scenario_pair_id, episode.scenario_pair_id),
            ("seed", item.seed, episode.seed),
            ("episode_id", item.episode_id, episode.episode_id),
        ):
            self._mismatch(
                item,
                field=f"episode.{field}",
                expected=expected,
                actual=actual,
                phase="episode_record",
                descriptor=item.identity.environment,
            )
        return episode

    def identity_generator_metadata(self, item: EpisodeSpec) -> dict[str, str]:
        generator = item.identity.environment
        configured = self.spec.config
        return {
            "name": str(configured.get("scenario_generator", "deterministic_synthetic_scenarios")),
            "version": str(configured.get("scenario_generator_version", "3.0.0")),
            "scenario_schema_version": str(configured.get("scenario_schema_version", "v2")),
            "environment_version": generator.version,
        }


class EpisodeScheduler:
    def __init__(
        self,
        runner: EpisodeRunner,
        workers: int = 1,
        retry_attempts: int = 0,
        failure_policy: str = "continue",
    ):
        self.runner, self.workers = runner, max(1, int(workers))
        self.retry_attempts, self.failure_policy = (
            max(0, int(retry_attempts)),
            failure_policy,
        )
        self.errors: list[OrchestrationError] = []

    def _run_one(self, item: EpisodeSpec) -> Episode | None:
        for attempt in range(1, self.retry_attempts + 2):
            try:
                return self.runner.run(item)
            except Exception as exc:
                if attempt <= self.retry_attempts and not isinstance(exc, IdentityMismatchError):
                    continue
                phase = exc.phase if isinstance(exc, (IdentityMismatchError, PluginIsolationError)) else "episode"
                failure_record = ActionRecord.infrastructure_failure(
                    error_type=type(exc).__name__,
                    message=str(exc),
                    phase=phase,
                )
                if isinstance(exc, IdentityMismatchError):
                    error = OrchestrationError(
                        item.episode_id,
                        exc.phase,
                        type(exc).__name__,
                        str(exc),
                        attempt,
                        exc.field,
                        exc.expected,
                        exc.actual,
                        exc.plugin_descriptor,
                        failure_record.to_dict(),
                        item.to_dict(),
                    )
                else:
                    error = OrchestrationError(
                        item.episode_id,
                        phase,
                        type(exc).__name__,
                        str(exc),
                        attempt,
                        action_record=failure_record.to_dict(),
                        planned_episode=item.to_dict(),
                        failure_details=exc.details if isinstance(exc, PluginIsolationError) else None,
                    )
                self.errors.append(error)
                if self.failure_policy == "fail_fast":
                    raise
                return None
        return None

    def run(self, plan: list[EpisodeSpec], completed: set[str] | None = None) -> list[Episode]:
        pending = [p for p in plan if p.episode_id not in (completed or set())]
        if self.workers == 1:
            return [episode for p in pending if (episode := self._run_one(p)) is not None]
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            return [episode for episode in pool.map(self._run_one, pending) if episode is not None]


class RunCoordinator:
    def __init__(self, spec: ExperimentSpec, catalog: PluginCatalog | None = None):
        self.spec, self.catalog = spec, catalog or PluginCatalog()
        self.errors: list[OrchestrationError] = []
        self.run_id: str | None = None
        self.identity: ExperimentIdentity | None = None
        self.scenario_specs: tuple[ScenarioSpec, ...] = ()

    def run(
        self,
        completed: set[str] | None = None,
        checkpoint_path: str | Path | None = None,
        scenario_manifest_dir: str | Path | None = None,
        scenario_manifest_writer: Callable[[ScenarioSpec], Path] | None = None,
    ) -> list[Episode]:
        planner = ExperimentPlanner(self.spec, self.catalog)
        self.run_id = planner.run_id
        self.identity = planner.identity
        scheduler = EpisodeScheduler(
            EpisodeRunner(self.spec, self.catalog),
            self.spec.workers,
            self.spec.retry_attempts,
            self.spec.failure_policy,
        )
        canonical_plan = planner.canonical_plan()
        self.scenario_specs = planner.scenario_specs()
        if scenario_manifest_dir is not None and scenario_manifest_writer is not None:
            raise ValueError("provide a scenario manifest directory or writer, not both")
        if scenario_manifest_writer is not None:
            for scenario in self.scenario_specs:
                scenario_manifest_writer(scenario)
        elif scenario_manifest_dir is not None:
            for scenario in self.scenario_specs:
                write_scenario_manifest(scenario_manifest_dir, scenario)
        if checkpoint_path and Path(checkpoint_path).exists():
            saved = canonical_loads(Path(checkpoint_path).read_text(encoding="utf-8"))
            saved_run_id = saved.get("run_id")
            if saved_run_id is not None and saved_run_id != planner.run_id:
                scenario_generator = planner.identity.semantic.scenario_generator
                episode_id = canonical_plan[0].episode_id if canonical_plan else planner.run_id
                mismatch = IdentityMismatchError(
                    field="checkpoint.run_id",
                    expected=planner.run_id,
                    actual=saved_run_id,
                    phase="checkpoint_identity",
                    plugin_descriptor=EpisodeRunner._descriptor_dict(scenario_generator),
                    episode_id=episode_id,
                )
                failure_record = ActionRecord.infrastructure_failure(
                    error_type=type(mismatch).__name__,
                    message=str(mismatch),
                    phase=mismatch.phase,
                )
                self.errors = [
                    OrchestrationError(
                        episode_id,
                        mismatch.phase,
                        type(mismatch).__name__,
                        str(mismatch),
                        1,
                        mismatch.field,
                        mismatch.expected,
                        mismatch.actual,
                        mismatch.plugin_descriptor,
                        failure_record.to_dict(),
                    )
                ]
                raise mismatch
            completed = set(completed or set()) | set(saved.get("completed_episode_ids", []))
        canonical_ids = {item.episode_id for item in canonical_plan}
        unknown_completed = set(completed or set()) - canonical_ids
        if unknown_completed:
            raise UnknownEpisodeSelectionError("resume", unknown_completed)
        try:
            episodes = scheduler.run(planner.plan(), completed)
        except Exception:
            self.errors = sorted(scheduler.errors, key=lambda error: error.episode_id)
            if checkpoint_path:
                path = Path(checkpoint_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                write_json(
                    path,
                    {
                        "run_id": planner.run_id,
                        "episode_record_version": EPISODE_RECORD_VERSION,
                        "action_record_contract": ACTION_RECORD_CONTRACT,
                        "counterfactual_evaluation_contract": COUNTERFACTUAL_EVALUATION_CONTRACT,
                        "scenario_manifest_contract": SCENARIO_MANIFEST_CONTRACT,
                        "scenario_family_contract": SCENARIO_FAMILY_CONTRACT,
                        "scenario_split_contract": SCENARIO_SPLIT_CONTRACT,
                        "completed_episode_ids": sorted(completed or set()),
                        "completed_scenario_pair_ids": sorted(
                            {
                                item.scenario_pair_id
                                for item in canonical_plan
                                if item.episode_id in set(completed or set())
                            }
                        ),
                        "scenario_manifest_hashes": sorted(scenario.content_hash for scenario in self.scenario_specs),
                        "errors": [e.to_dict() for e in self.errors],
                    },
                )
            raise
        self.errors = sorted(scheduler.errors, key=lambda error: error.episode_id)
        if checkpoint_path:
            path = Path(checkpoint_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(
                path,
                {
                    "run_id": planner.run_id,
                    "episode_record_version": EPISODE_RECORD_VERSION,
                    "action_record_contract": ACTION_RECORD_CONTRACT,
                    "counterfactual_evaluation_contract": COUNTERFACTUAL_EVALUATION_CONTRACT,
                    "scenario_manifest_contract": SCENARIO_MANIFEST_CONTRACT,
                    "scenario_family_contract": SCENARIO_FAMILY_CONTRACT,
                    "scenario_split_contract": SCENARIO_SPLIT_CONTRACT,
                    "completed_episode_ids": sorted((completed or set()) | {e.episode_id for e in episodes}),
                    "completed_scenario_pair_ids": sorted(
                        {
                            item.scenario_pair_id
                            for item in canonical_plan
                            if item.episode_id in ((completed or set()) | {episode.episode_id for episode in episodes})
                        }
                    ),
                    "scenario_manifest_hashes": sorted(scenario.content_hash for scenario in self.scenario_specs),
                    "errors": [e.to_dict() for e in self.errors],
                },
            )
        return sorted(episodes, key=lambda e: e.episode_id)
