"""Pure typed configuration schema version 2 and legacy migration."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from tool_agent_shift_benchmark.core.config import load_raw_config, write_config_yaml
from tool_agent_shift_benchmark.core.monitoring import MONITOR_MODES
from tool_agent_shift_benchmark.core.oversight import LEGACY_OVERSIGHT_ALIASES, OVERSIGHT_MODES
from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass

CONFIG_SCHEMA_VERSION = 2
PLUGIN_CONTRACT_VERSION = "1"

BUILTIN_COMPONENTS: dict[str, frozenset[str]] = {
    "environment": frozenset({"file_ops", "calendar_ops", "risk_ops"}),
    "agent": frozenset(
        {
            "naive",
            "retry",
            "validate_then_act",
            "conservative",
            "offline_llm_fixture",
            "monitor_gated",
        }
    ),
    "shift": frozenset(
        {
            "normal",
            "schema_drift",
            "stale_observation",
            "latency_spike",
            "missing_field",
            "conflicting_tool_output",
            "corrupted_memory",
            "constraint_shift",
            "compound_shift",
        }
    ),
    "monitor": frozenset({"composite"}),
    "reporter": frozenset(),
}

ALLOWED_KEYS = frozenset(
    {
        "schema_version",
        "environments",
        "agents",
        "faults",
        "shift_chains",
        "fault_severities",
        "fault_schedules",
        "episodes_per_combo",
        "episode_steps",
        "workers",
        "monitor",
        "monitor_policy",
        "monitor_modes",
        "oversight_modes",
        "failure_policy",
        "retry_attempts",
        "requery_attempts",
        "artifact_policy",
        "episode_ids",
        "scenario_indices",
        "selection_offset",
        "selection_limit",
        "partition_index",
        "partition_count",
        "replay_episode_ids",
        "resume_episode_ids",
        "seeds",
        "seed",
        "fault_pairs",
        "plugin_references",
        "scenario_generator",
        "scenario_generator_version",
        "scenario_schema_version",
        "scenario_split",
        "scenario_splits",
        "scenario_manifest_path",
        "evaluator",
        "evaluator_version",
        "policy_resources",
        "logging",
        "output_path",
        "working_directory",
        "progress_display",
        "execution_batch_size",
        "migration",
    }
)

LEGACY_ALLOWED_KEYS = ALLOWED_KEYS - {
    "plugin_references",
    "fault_schedules",
    "scenario_splits",
    "migration",
}


class ConfigValidationError(ValueError):
    def __init__(self, path: str, message: str, source: str = "<config>"):
        self.path = path
        self.message = message
        self.source = source
        super().__init__(f"{source}:{path}: {message}")


@dataclass(frozen=True)
class PluginReferenceConfig:
    kind: str
    name: str
    version: str
    contract_version: str
    entry_point: str


@dataclass(frozen=True)
class FaultScheduleConfig:
    shift_chain: tuple[str, ...]
    configured_severity: float
    onset_step: int
    duration: int | None
    persistence: str
    recurrence: int | None
    per_step_severity: tuple[float, ...]

    @property
    def severity(self) -> float:
        return self.configured_severity

    @property
    def start_step(self) -> int:
        return self.onset_step

    @property
    def end_step(self) -> int:
        if self.duration is None:
            raise AttributeError("persistent schedule has no finite end_step")
        return self.onset_step + self.duration - 1

    @property
    def cadence(self) -> str:
        return "each_step" if self.recurrence is None else f"every_{self.recurrence}_steps"


@dataclass(frozen=True)
class ScenarioSplitConfig:
    name: str
    indices: tuple[int, ...]


@dataclass(frozen=True)
class MigrationMetadata:
    source_schema_version: str
    decisions: tuple[str, ...]


@dataclass(frozen=True)
class ConfigV2:
    schema_version: int
    environments: tuple[str, ...]
    agents: tuple[str, ...]
    faults: tuple[str, ...]
    shift_chains: tuple[tuple[str, ...], ...]
    fault_severities: tuple[float, ...]
    fault_schedules: tuple[FaultScheduleConfig, ...]
    episodes_per_combo: int
    episode_steps: int
    workers: int
    monitor: str
    monitor_policy: str
    monitor_modes: tuple[str, ...]
    oversight_modes: tuple[str, ...]
    failure_policy: str
    retry_attempts: int
    requery_attempts: int
    artifact_policy: str
    episode_ids: tuple[str, ...]
    scenario_indices: tuple[int, ...]
    selection_offset: int
    selection_limit: int | None
    partition_index: int | None
    partition_count: int | None
    replay_episode_ids: tuple[str, ...]
    resume_episode_ids: tuple[str, ...]
    seeds: tuple[int, ...]
    seed: int
    fault_pairs: tuple[str, ...]
    plugin_references: tuple[PluginReferenceConfig, ...]
    scenario_generator: str
    scenario_generator_version: str
    scenario_schema_version: str
    scenario_split: str
    scenario_splits: tuple[ScenarioSplitConfig, ...]
    scenario_manifest_path: str
    evaluator: str
    evaluator_version: str
    policy_resources: dict[str, str]
    logging: str
    output_path: str
    working_directory: str
    progress_display: bool
    execution_batch_size: int
    migration: MigrationMetadata | None

    def to_dict(self) -> dict[str, Any]:
        normalized = canonicalize(self)
        if not isinstance(normalized, dict):
            raise RuntimeError("normalized configuration did not produce a mapping")
        return normalized


def _error(source: str, path: str, message: str) -> ConfigValidationError:
    return ConfigValidationError(path, message, source)


def _mapping(value: Any, source: str, path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise _error(source, path, "must be a mapping")
    for key in value:
        if not isinstance(key, str):
            raise _error(source, path, "mapping keys must be strings")
    return value


def _check_keys(value: Mapping[str, Any], allowed: set[str] | frozenset[str], source: str, path: str) -> None:
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise _error(source, f"{path}.{unknown[0]}", "unknown key")


def _list(value: Any, source: str, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise _error(source, path, "must be a list")
    return value


def _string(value: Any, source: str, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(source, path, "must be a non-empty string")
    return value


def _integer(value: Any, source: str, path: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise _error(source, path, "must be an integer")
    if minimum is not None and value < minimum:
        raise _error(source, path, f"must be at least {minimum}")
    return value


def _number(value: Any, source: str, path: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise _error(source, path, "must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise _error(source, path, "must be finite")
    return normalized


def _unique(values: Sequence[Any], source: str, path: str) -> None:
    seen: set[Any] = set()
    for index, value in enumerate(values):
        marker = tuple(value) if isinstance(value, list) else value
        if marker in seen:
            raise _error(source, f"{path}[{index}]", f"duplicate value {value!r}")
        seen.add(marker)


def _string_list(value: Any, source: str, path: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    items = _list(value, source, path)
    if not allow_empty and not items:
        raise _error(source, path, "must not be empty")
    normalized = tuple(_string(item, source, f"{path}[{index}]") for index, item in enumerate(items))
    _unique(normalized, source, path)
    return normalized


def _int_list(value: Any, source: str, path: str, *, minimum: int = 0) -> tuple[int, ...]:
    items = _list(value, source, path)
    normalized = tuple(_integer(item, source, f"{path}[{index}]", minimum=minimum) for index, item in enumerate(items))
    _unique(normalized, source, path)
    return normalized


def _plugin_references(value: Any, source: str) -> tuple[PluginReferenceConfig, ...]:
    references: list[PluginReferenceConfig] = []
    for index, raw in enumerate(_list(value, source, "$.plugin_references")):
        path = f"$.plugin_references[{index}]"
        item = _mapping(raw, source, path)
        _check_keys(item, {"kind", "name", "version", "contract_version", "entry_point"}, source, path)
        kind = _string(item.get("kind"), source, f"{path}.kind")
        if kind not in BUILTIN_COMPONENTS:
            raise _error(source, f"{path}.kind", f"unsupported plugin kind {kind!r}")
        contract_version = _string(item.get("contract_version"), source, f"{path}.contract_version")
        if contract_version != PLUGIN_CONTRACT_VERSION:
            raise _error(
                source,
                f"{path}.contract_version",
                f"must equal supported contract version {PLUGIN_CONTRACT_VERSION!r}",
            )
        references.append(
            PluginReferenceConfig(
                kind,
                _string(item.get("name"), source, f"{path}.name"),
                _string(item.get("version"), source, f"{path}.version"),
                contract_version,
                _string(item.get("entry_point"), source, f"{path}.entry_point"),
            )
        )
    keys = [(reference.kind, reference.name) for reference in references]
    _unique(keys, source, "$.plugin_references")
    return tuple(sorted(references, key=lambda reference: (reference.kind, reference.name)))


def _known_components(references: Sequence[PluginReferenceConfig]) -> dict[str, set[str]]:
    known = {kind: set(names) for kind, names in BUILTIN_COMPONENTS.items()}
    for reference in references:
        known[reference.kind].add(reference.name)
    return known


def _require_known(values: Sequence[str], known: set[str], source: str, path: str) -> None:
    for index, value in enumerate(values):
        if value not in known:
            raise _error(source, f"{path}[{index}]", f"unknown component {value!r}")


def _fault_pair(value: Any, source: str, path: str, known_shifts: set[str]) -> str:
    raw = _string(value, source, path)
    parts = [part.strip() for part in raw.replace(",", "+").split("+") if part.strip()]
    if len(parts) != 2:
        raise _error(source, path, "must contain exactly two fault names")
    if parts[0] == parts[1]:
        raise _error(source, path, "must contain two distinct faults")
    for part in parts:
        if part not in known_shifts or part in {"normal", "compound_shift"}:
            raise _error(source, path, f"unsupported pairwise fault {part!r}")
    return "+".join(parts)


def _migration_metadata(value: Any, source: str) -> MigrationMetadata | None:
    if value is None:
        return None
    item = _mapping(value, source, "$.migration")
    _check_keys(item, {"source_schema_version", "decisions"}, source, "$.migration")
    return MigrationMetadata(
        _string(item.get("source_schema_version"), source, "$.migration.source_schema_version"),
        _string_list(item.get("decisions"), source, "$.migration.decisions"),
    )


def parse_config_data(data: dict[str, Any], *, source: str = "<config>", pairwise: bool = False) -> ConfigV2:
    root = _mapping(data, source, "$")
    _check_keys(root, ALLOWED_KEYS, source, "$")
    version = root.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version != CONFIG_SCHEMA_VERSION:
        raise _error(source, "$.schema_version", "must be integer 2; use `tasb config migrate` for legacy files")

    references = _plugin_references(root.get("plugin_references", []), source)
    known = _known_components(references)
    environments = _string_list(root.get("environments", ["file_ops"]), source, "$.environments", allow_empty=False)
    agents = _string_list(root.get("agents", ["naive"]), source, "$.agents", allow_empty=False)
    legacy_monitor_gated = "monitor_gated" in agents
    faults = _string_list(root.get("faults", ["normal"]), source, "$.faults", allow_empty=False)
    _require_known(environments, known["environment"], source, "$.environments")
    _require_known(agents, known["agent"], source, "$.agents")
    agents = tuple(dict.fromkeys("naive" if agent == "monitor_gated" else agent for agent in agents))
    _require_known(faults, known["shift"], source, "$.faults")

    raw_chains = root.get("shift_chains")
    if raw_chains is None:
        shift_chains = tuple((fault,) for fault in faults)
    else:
        chains: list[tuple[str, ...]] = []
        for index, raw_chain in enumerate(_list(raw_chains, source, "$.shift_chains")):
            chain = _string_list(raw_chain, source, f"$.shift_chains[{index}]", allow_empty=False)
            _require_known(chain, known["shift"], source, f"$.shift_chains[{index}]")
            chains.append(chain)
        if not chains:
            raise _error(source, "$.shift_chains", "must not be empty")
        _unique(chains, source, "$.shift_chains")
        shift_chains = tuple(chains)

    severities = tuple(
        _number(value, source, f"$.fault_severities[{index}]")
        for index, value in enumerate(_list(root.get("fault_severities", [1.0]), source, "$.fault_severities"))
    )
    if not severities:
        raise _error(source, "$.fault_severities", "must not be empty")
    _unique(severities, source, "$.fault_severities")
    for index, severity in enumerate(severities):
        if not 0.0 <= severity <= 1.0:
            raise _error(source, f"$.fault_severities[{index}]", "must be between 0.0 and 1.0")

    episodes_per_combo = _integer(root.get("episodes_per_combo", 3), source, "$.episodes_per_combo", minimum=1)
    episode_steps = _integer(root.get("episode_steps", 6), source, "$.episode_steps", minimum=1)
    workers = _integer(root.get("workers", 1), source, "$.workers", minimum=1)

    derived_schedules = tuple(
        FaultScheduleConfig(
            chain,
            severity,
            0,
            None,
            "persistent",
            None,
            (0.0 if chain == ("normal",) else severity,),
        )
        for chain in shift_chains
        for severity in severities
        if not (chain == ("normal",) and severity != 1.0)
    )
    raw_schedules = root.get("fault_schedules")
    if raw_schedules is None:
        fault_schedules = derived_schedules
    else:
        schedules: list[FaultScheduleConfig] = []
        for index, raw_schedule in enumerate(_list(raw_schedules, source, "$.fault_schedules")):
            path = f"$.fault_schedules[{index}]"
            item = _mapping(raw_schedule, source, path)
            chain = _string_list(item.get("shift_chain"), source, f"{path}.shift_chain", allow_empty=False)
            _require_known(chain, known["shift"], source, f"{path}.shift_chain")
            legacy_keys = {"shift_chain", "severity", "start_step", "end_step", "cadence"}
            current_keys = {
                "shift_chain",
                "configured_severity",
                "onset_step",
                "duration",
                "persistence",
                "recurrence",
                "per_step_severity",
            }
            if set(item).issubset(legacy_keys):
                _check_keys(item, legacy_keys, source, path)
                severity = _number(item.get("severity"), source, f"{path}.severity")
                onset = _integer(item.get("start_step"), source, f"{path}.start_step", minimum=0)
                end = _integer(item.get("end_step"), source, f"{path}.end_step", minimum=onset)
                if end >= episode_steps:
                    raise _error(source, f"{path}.end_step", "must be less than episode_steps")
                cadence = _string(item.get("cadence"), source, f"{path}.cadence")
                if cadence != "each_step":
                    raise _error(source, f"{path}.cadence", "legacy schedules support only 'each_step'")
                schedules.append(
                    FaultScheduleConfig(
                        chain,
                        severity,
                        onset,
                        end - onset + 1,
                        "transient",
                        None,
                        (severity,),
                    )
                )
                continue
            _check_keys(item, current_keys, source, path)
            configured = _number(
                item.get("configured_severity"),
                source,
                f"{path}.configured_severity",
            )
            onset = _integer(item.get("onset_step"), source, f"{path}.onset_step", minimum=0)
            if onset >= episode_steps:
                raise _error(source, f"{path}.onset_step", "must be less than episode_steps")
            persistence = _string(item.get("persistence"), source, f"{path}.persistence")
            if persistence not in {"persistent", "transient"}:
                raise _error(source, f"{path}.persistence", "must be 'persistent' or 'transient'")
            raw_duration = item.get("duration")
            duration = None if raw_duration is None else _integer(raw_duration, source, f"{path}.duration", minimum=1)
            raw_recurrence = item.get("recurrence")
            recurrence = (
                None if raw_recurrence is None else _integer(raw_recurrence, source, f"{path}.recurrence", minimum=1)
            )
            if persistence == "persistent" and (duration is not None or recurrence is not None):
                raise _error(source, path, "persistent schedules cannot declare duration or recurrence")
            if persistence == "transient" and duration is None:
                raise _error(source, f"{path}.duration", "transient schedules require a duration")
            if duration is not None and onset + duration > episode_steps and recurrence is None:
                raise _error(source, f"{path}.duration", "active window exceeds episode_steps")
            if recurrence is not None and duration is not None and recurrence <= duration:
                raise _error(source, f"{path}.recurrence", "must be greater than duration")
            profile = tuple(
                _number(value, source, f"{path}.per_step_severity[{profile_index}]")
                for profile_index, value in enumerate(
                    _list(item.get("per_step_severity"), source, f"{path}.per_step_severity")
                )
            )
            if not profile:
                raise _error(source, f"{path}.per_step_severity", "must not be empty")
            for profile_index, value in enumerate(profile):
                if not 0.0 <= value <= 1.0:
                    raise _error(
                        source,
                        f"{path}.per_step_severity[{profile_index}]",
                        "must be between 0.0 and 1.0",
                    )
            schedules.append(
                FaultScheduleConfig(
                    chain,
                    configured,
                    onset,
                    duration,
                    persistence,
                    recurrence,
                    profile,
                )
            )
        fault_schedules = tuple(schedules)
        actual_treatments = {(schedule.shift_chain, schedule.configured_severity) for schedule in fault_schedules}
        expected_treatments = {(schedule.shift_chain, schedule.configured_severity) for schedule in derived_schedules}
        if actual_treatments != expected_treatments:
            raise _error(source, "$.fault_schedules", "must cover exactly the configured shift/severity matrix")

    monitor = _string(root.get("monitor", "composite"), source, "$.monitor")
    _require_known((monitor,), known["monitor"], source, "$.monitor")
    raw_monitor_policy = root.get("monitor_policy")
    raw_oversight_modes = root.get("oversight_modes")
    if raw_oversight_modes is None:
        monitor_policy = _string(
            raw_monitor_policy if raw_monitor_policy is not None else "gate", source, "$.monitor_policy"
        )
        if monitor_policy not in LEGACY_OVERSIGHT_ALIASES:
            raise _error(source, "$.monitor_policy", "must be legacy alias 'record' or 'gate'")
        oversight_modes = (LEGACY_OVERSIGHT_ALIASES[monitor_policy],)
    else:
        monitor_policy = _string(
            raw_monitor_policy if raw_monitor_policy is not None else "independent", source, "$.monitor_policy"
        )
        oversight_modes = _string_list(raw_oversight_modes, source, "$.oversight_modes", allow_empty=False)
        for index, mode in enumerate(oversight_modes):
            if mode not in OVERSIGHT_MODES:
                raise _error(source, f"$.oversight_modes[{index}]", f"unknown oversight mode {mode!r}")
            if mode in oversight_modes[:index]:
                raise _error(source, f"$.oversight_modes[{index}]", f"duplicate oversight mode {mode!r}")
        if monitor_policy in LEGACY_OVERSIGHT_ALIASES:
            if oversight_modes != (LEGACY_OVERSIGHT_ALIASES[monitor_policy],):
                raise _error(source, "$.monitor_policy", "legacy monitor policy must match the sole oversight mode")
        elif monitor_policy != "independent":
            raise _error(source, "$.monitor_policy", "must be 'independent' with explicit oversight_modes")
    monitor_modes = _string_list(root.get("monitor_modes", []), source, "$.monitor_modes")
    for index, mode in enumerate(monitor_modes):
        if mode not in MONITOR_MODES:
            raise _error(source, f"$.monitor_modes[{index}]", f"unknown monitor mode {mode!r}")
        if mode in monitor_modes[:index]:
            raise _error(source, f"$.monitor_modes[{index}]", f"duplicate monitor mode {mode!r}")
    if monitor != "composite" and monitor_modes:
        raise _error(source, "$.monitor_modes", "custom monitor plugins cannot be combined with built-in modes")
    if legacy_monitor_gated:
        monitor_policy = "independent"
        oversight_modes = tuple(dict.fromkeys((*oversight_modes, "hard_gate")))
        monitor_modes = tuple(dict.fromkeys((*monitor_modes, "full_composite_monitor")))

    failure_policy = _string(root.get("failure_policy", "continue"), source, "$.failure_policy")
    if failure_policy not in {"continue", "fail_fast"}:
        raise _error(source, "$.failure_policy", "must be 'continue' or 'fail_fast'")
    retry_attempts = _integer(root.get("retry_attempts", 0), source, "$.retry_attempts", minimum=0)
    requery_attempts = _integer(root.get("requery_attempts", 2), source, "$.requery_attempts", minimum=0)
    artifact_policy = _string(root.get("artifact_policy", "bundle"), source, "$.artifact_policy")
    if artifact_policy not in {"bundle", "legacy", "both"}:
        raise _error(source, "$.artifact_policy", "must be 'bundle', 'legacy', or 'both'")

    episode_ids = _string_list(root.get("episode_ids", []), source, "$.episode_ids")
    scenario_indices = _int_list(root.get("scenario_indices", []), source, "$.scenario_indices")
    selection_offset = _integer(root.get("selection_offset", 0), source, "$.selection_offset", minimum=0)
    raw_limit = root.get("selection_limit")
    selection_limit = None if raw_limit is None else _integer(raw_limit, source, "$.selection_limit", minimum=0)
    raw_partition_index = root.get("partition_index")
    raw_partition_count = root.get("partition_count")
    if (raw_partition_index is None) != (raw_partition_count is None):
        raise _error(source, "$.partition_index", "partition_index and partition_count must be provided together")
    partition_index = (
        None if raw_partition_index is None else _integer(raw_partition_index, source, "$.partition_index", minimum=0)
    )
    partition_count = (
        None if raw_partition_count is None else _integer(raw_partition_count, source, "$.partition_count", minimum=1)
    )
    if partition_index is not None and partition_count is not None and partition_index >= partition_count:
        raise _error(source, "$.partition_index", "must be less than partition_count")
    replay_episode_ids = _string_list(root.get("replay_episode_ids", []), source, "$.replay_episode_ids")
    resume_episode_ids = _string_list(root.get("resume_episode_ids", []), source, "$.resume_episode_ids")
    if episode_ids and replay_episode_ids:
        raise _error(source, "$.replay_episode_ids", "cannot be combined with episode_ids")

    seeds = _int_list(root.get("seeds", []), source, "$.seeds", minimum=0)
    seed = _integer(root.get("seed", 42), source, "$.seed", minimum=0)
    fault_pairs = tuple(
        _fault_pair(value, source, f"$.fault_pairs[{index}]", known["shift"])
        for index, value in enumerate(_list(root.get("fault_pairs", []), source, "$.fault_pairs"))
    )
    pair_keys = [tuple(sorted(pair.split("+"))) for pair in fault_pairs]
    _unique(pair_keys, source, "$.fault_pairs")
    if pairwise and not fault_pairs:
        raise _error(source, "$.fault_pairs", "pairwise configuration requires at least one fault pair")

    scenario_generator = _string(
        root.get("scenario_generator", "deterministic_synthetic_scenarios"),
        source,
        "$.scenario_generator",
    )
    scenario_generator_version = _string(
        root.get("scenario_generator_version", "2.1.0"), source, "$.scenario_generator_version"
    )
    scenario_schema_version = _string(root.get("scenario_schema_version", "v1"), source, "$.scenario_schema_version")
    scenario_split = _string(root.get("scenario_split", "default"), source, "$.scenario_split")
    scenario_manifest_path = root.get("scenario_manifest_path", "")
    if not isinstance(scenario_manifest_path, str):
        raise _error(source, "$.scenario_manifest_path", "must be a string")
    raw_splits = root.get("scenario_splits")
    if raw_splits is None:
        scenario_splits = (ScenarioSplitConfig("default", tuple(range(episodes_per_combo))),)
    else:
        splits: list[ScenarioSplitConfig] = []
        for index, raw_split in enumerate(_list(raw_splits, source, "$.scenario_splits")):
            path = f"$.scenario_splits[{index}]"
            item = _mapping(raw_split, source, path)
            _check_keys(item, {"name", "indices"}, source, path)
            name = _string(item.get("name"), source, f"{path}.name")
            indices = tuple(sorted(_int_list(item.get("indices"), source, f"{path}.indices")))
            for split_index in indices:
                if split_index >= episodes_per_combo:
                    raise _error(source, f"{path}.indices", "indices must be less than episodes_per_combo")
            splits.append(ScenarioSplitConfig(name, indices))
        _unique([split.name for split in splits], source, "$.scenario_splits")
        scenario_splits = tuple(sorted(splits, key=lambda split: split.name))
    if scenario_split not in {split.name for split in scenario_splits}:
        raise _error(source, "$.scenario_split", "must name one of scenario_splits")

    evaluator = _string(root.get("evaluator", "hidden_state_evaluator"), source, "$.evaluator")
    evaluator_version = _string(root.get("evaluator_version", "1.0.0"), source, "$.evaluator_version")
    raw_resources = _mapping(root.get("policy_resources", {}), source, "$.policy_resources")
    resources: dict[str, str] = {}
    for name, raw_digest in raw_resources.items():
        digest = _string(raw_digest, source, f"$.policy_resources.{name}").lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise _error(source, f"$.policy_resources.{name}", "must be a 64-character SHA-256 hash")
        resources[name] = digest

    logging = _string(root.get("logging", "standard"), source, "$.logging")
    if logging not in {"quiet", "standard", "verbose"}:
        raise _error(source, "$.logging", "must be 'quiet', 'standard', or 'verbose'")
    output_path = _string(root.get("output_path", "results"), source, "$.output_path")
    working_directory = root.get("working_directory", "")
    if not isinstance(working_directory, str):
        raise _error(source, "$.working_directory", "must be a string")
    progress_display = root.get("progress_display", True)
    if not isinstance(progress_display, bool):
        raise _error(source, "$.progress_display", "must be a boolean")
    execution_batch_size = _integer(root.get("execution_batch_size", 1), source, "$.execution_batch_size", minimum=1)

    return ConfigV2(
        CONFIG_SCHEMA_VERSION,
        environments,
        agents,
        faults,
        shift_chains,
        severities,
        fault_schedules,
        episodes_per_combo,
        episode_steps,
        workers,
        monitor,
        monitor_policy,
        monitor_modes,
        oversight_modes,
        failure_policy,
        retry_attempts,
        requery_attempts,
        artifact_policy,
        episode_ids,
        scenario_indices,
        selection_offset,
        selection_limit,
        partition_index,
        partition_count,
        replay_episode_ids,
        resume_episode_ids,
        seeds,
        seed,
        fault_pairs,
        references,
        scenario_generator,
        scenario_generator_version,
        scenario_schema_version,
        scenario_split,
        scenario_splits,
        scenario_manifest_path,
        evaluator,
        evaluator_version,
        {key: resources[key] for key in sorted(resources)},
        logging,
        output_path,
        working_directory,
        progress_display,
        execution_batch_size,
        _migration_metadata(root.get("migration"), source),
    )


def validate_config_data(data: dict[str, Any], *, pairwise: bool = False) -> list[str]:
    parse_config_data(data, pairwise=pairwise)
    return []


def validate_config(path: str | Path, *, pairwise: bool = False) -> list[str]:
    parse_config_data(load_raw_config(path), source=str(path), pairwise=pairwise)
    return []


def migrate_config_data(data: dict[str, Any], *, source: str = "<config>") -> tuple[ConfigV2, tuple[str, ...]]:
    version = data.get("schema_version")
    if version == CONFIG_SCHEMA_VERSION and isinstance(version, int) and not isinstance(version, bool):
        return parse_config_data(data, source=source), ()
    if version not in {None, 1, "1", "1.0"}:
        raise _error(source, "$.schema_version", f"unsupported legacy schema version {version!r}")
    _check_keys(_mapping(data, source, "$"), LEGACY_ALLOWED_KEYS, source, "$")
    migrated = {key: value for key, value in data.items() if key != "schema_version"}
    decisions: list[str] = []
    if "monitor_policy" not in migrated:
        migrated["monitor_policy"] = "record"
        decisions.append("monitor_policy was absent; selected 'record' to preserve the legacy file-runner behavior")
    if "faults" in migrated and "shift_chains" in migrated:
        faults = migrated["faults"]
        chains = migrated["shift_chains"]
        if not isinstance(faults, list) or not isinstance(chains, list) or chains != [[fault] for fault in faults]:
            raise _error(
                source,
                "$.shift_chains",
                "ambiguous legacy values: faults and shift_chains disagree; resolve them before migration",
            )
    migrated["schema_version"] = CONFIG_SCHEMA_VERSION
    migrated["migration"] = {
        "source_schema_version": "1" if version is not None else "unversioned-v1",
        "decisions": decisions,
    }
    model = parse_config_data(migrated, source=source)
    return model, tuple(decisions)


def migrate_config(path: str | Path, output: str | Path | None = None) -> tuple[ConfigV2, tuple[str, ...]]:
    model, decisions = migrate_config_data(load_raw_config(path), source=str(path))
    if output is not None:
        write_config_yaml(output, model.to_dict())
    return model, decisions


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate Tool-Agent Shift Benchmark config schema v2")
    parser.add_argument("path")
    parser.add_argument("--pairwise", action="store_true")
    args = parser.parse_args(argv)
    validate_config(args.path, pairwise=args.pairwise)
    print(f"config valid (schema v2): {args.path}")


for _config_dataclass in (
    PluginReferenceConfig,
    FaultScheduleConfig,
    ScenarioSplitConfig,
    MigrationMetadata,
    ConfigV2,
):
    register_dataclass(_config_dataclass)


if __name__ == "__main__":
    main()
