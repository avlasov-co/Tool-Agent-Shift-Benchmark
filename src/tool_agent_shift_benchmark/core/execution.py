"""One normalized planning and execution path for every experiment mode.

Command modules deliberately stay thin.  They translate their compatibility
flags into :class:`ExecutionRequest`; this module then constructs the one
``ExperimentSpec``/``ExperimentPlanner``/``RunCoordinator`` path used by all
ordinary, sweep, seed, pairwise, replay, and resume work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.competence import run_clean_competence_preflight
from tool_agent_shift_benchmark.core.config import load_config
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.orchestration import (
    EpisodeSpec,
    ExperimentPlanner,
    ExperimentSpec,
    RunCoordinator,
)

EXECUTION_REQUEST_SCHEMA_VERSION = "execution-request-v1"
EXECUTION_PLAN_SCHEMA_VERSION = "execution-plan-v1"
EXECUTION_RESULT_SCHEMA_VERSION = "execution-result-v1"
EXECUTION_MODES = frozenset(
    {
        "ordinary",
        "seed_sweep",
        "severity_sweep",
        "monitor_ablation",
        "pairwise_compound",
        "replay",
        "resume",
    }
)


@dataclass(frozen=True)
class ExecutionRequest:
    """Operational request that is normalized before any planning occurs."""

    config_path: str
    mode: str = "ordinary"
    seed: int | None = None
    environments: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    all_environments: bool = False
    all_agents: bool = False
    workers: int | None = None
    scenario_indices: tuple[int, ...] = ()
    episode_ids: tuple[str, ...] = ()
    selection_offset: int | None = None
    selection_limit: int | None = None
    partition_index: int | None = None
    partition_count: int | None = None
    replay_episode_ids: tuple[str, ...] = ()
    monitor_modes: tuple[str, ...] = ()
    oversight_modes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in EXECUTION_MODES:
            raise ValueError(f"unsupported execution mode {self.mode!r}")
        if self.mode == "replay" and not self.replay_episode_ids:
            raise ValueError("replay execution requires replay_episode_ids")
        if self.mode != "replay" and self.replay_episode_ids:
            raise ValueError("replay_episode_ids require replay execution mode")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": EXECUTION_REQUEST_SCHEMA_VERSION,
            "mode": self.mode,
            "config_path": self.config_path,
            "seed": self.seed,
            "environments": list(self.environments),
            "agents": list(self.agents),
            "all_environments": self.all_environments,
            "all_agents": self.all_agents,
            "workers": self.workers,
            "scenario_indices": list(self.scenario_indices),
            "episode_ids": list(self.episode_ids),
            "selection_offset": self.selection_offset,
            "selection_limit": self.selection_limit,
            "partition_index": self.partition_index,
            "partition_count": self.partition_count,
            "replay_episode_ids": list(self.replay_episode_ids),
            "monitor_modes": list(self.monitor_modes),
            "oversight_modes": list(self.oversight_modes),
        }


@dataclass(frozen=True)
class ExecutionPlan:
    """The resolved plan plus the normalized request that produced it."""

    request: ExecutionRequest
    normalized_config: dict[str, Any]
    spec: ExperimentSpec
    planner: ExperimentPlanner
    episodes: tuple[EpisodeSpec, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
            "execution_mode": self.request.mode,
            "request": self.request.to_dict(),
            "run_id": self.planner.run_id,
            "config_digest": self.planner.config_digest,
            "identity": self.planner.identity.to_dict(),
            "normalized_config": self.normalized_config,
            "dimensions": {
                "environments": list(self.spec.environments),
                "agents": list(self.spec.agents),
                "shift_chains": [list(chain) for chain in self.spec.shift_chains],
                "severities": list(self.spec.severities),
                "monitor_modes": list(self.spec.monitor_modes),
                "oversight_modes": list(self.spec.oversight_modes),
                "scenario_split": self.planner.identity.semantic.scenario_split,
                "seed": self.spec.seed,
            },
            "episodes": [item.to_dict() for item in self.episodes],
        }


@dataclass(frozen=True)
class ExecutionResult:
    plan: ExecutionPlan
    episodes: tuple[Episode, ...]
    orchestration_errors: tuple[dict[str, Any], ...]
    competence_report: dict[str, Any]
    scenario_specs: tuple[Any, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": EXECUTION_RESULT_SCHEMA_VERSION,
            "plan": self.plan.to_dict(),
            "completed_episode_ids": [episode.episode_id for episode in self.episodes],
            "orchestration_errors": list(self.orchestration_errors),
            "competence_report": self.competence_report,
            "scenario_count": len(self.scenario_specs),
        }


def _catalog_names(catalog: PluginCatalog, kind: str) -> tuple[str, ...]:
    return tuple(sorted(descriptor.name for descriptor in catalog.descriptors() if descriptor.kind == kind))


def normalize_execution_request(
    request: ExecutionRequest,
    *,
    catalog: PluginCatalog | None = None,
) -> ExecutionPlan:
    """Normalize every command/API request before construction of an identity."""

    return plan_execution_config(request, load_config(request.config_path), catalog=catalog)


def plan_execution_config(
    request: ExecutionRequest,
    source_config: dict[str, Any],
    *,
    catalog: PluginCatalog | None = None,
) -> ExecutionPlan:
    """Plan an already-loaded configuration through the same normalizer.

    Pairwise and seed wrappers use this public helper instead of constructing
    identities or ``EpisodeSpec`` values themselves.
    """

    catalog = catalog or PluginCatalog()
    environments = (
        _catalog_names(catalog, "environment")
        if request.all_environments
        else request.environments or tuple(str(value) for value in source_config.get("environments", ()))
    )
    agents = (
        _catalog_names(catalog, "agent")
        if request.all_agents
        else request.agents or tuple(str(value) for value in source_config.get("agents", ()))
    )
    if not environments or not agents:
        raise ValueError("execution requires at least one environment and one agent")
    normalized = {
        **source_config,
        "environments": list(environments),
        "agents": list(agents),
        "_config_path": request.config_path,
        "_working_directory": str(Path.cwd()),
        "_execution_mode": request.mode,
    }
    if request.monitor_modes:
        normalized["monitor_modes"] = list(request.monitor_modes)
    if request.oversight_modes:
        normalized.pop("monitor_policy", None)
        normalized["oversight_modes"] = list(request.oversight_modes)
    spec = ExperimentSpec.from_config(
        normalized,
        seed=request.seed,
        environments=environments,
        agents=agents,
        workers=request.workers,
        scenario_indices=request.scenario_indices or None,
        episode_ids=request.episode_ids or None,
        selection_offset=request.selection_offset,
        selection_limit=request.selection_limit,
        partition_index=request.partition_index,
        partition_count=request.partition_count,
        replay_episode_ids=request.replay_episode_ids or None,
    )
    planner = ExperimentPlanner(spec, catalog)
    return ExecutionPlan(request, normalized, spec, planner, tuple(planner.plan()))


def _unique_episodes(episodes: Iterable[Episode], *, planned_order: Iterable[str] | None = None) -> tuple[Episode, ...]:
    by_id: dict[str, Episode] = {}
    for episode in episodes:
        existing = by_id.get(episode.episode_id)
        if existing is not None and existing.to_dict() != episode.to_dict():
            raise ValueError(f"duplicate episode ID has divergent records: {episode.episode_id}")
        by_id[episode.episode_id] = episode
    order = tuple(planned_order or ())
    if order:
        missing = set(by_id) - set(order)
        if missing:
            raise ValueError(f"completed episode IDs are absent from the normalized plan: {sorted(missing)!r}")
        return tuple(by_id[episode_id] for episode_id in order if episode_id in by_id)
    return tuple(by_id[episode_id] for episode_id in sorted(by_id))


def execute_plan(
    plan: ExecutionPlan,
    *,
    existing_episodes: Iterable[Episode] = (),
    checkpoint_path: str | Path | None = None,
    scenario_manifest_dir: str | Path | None = None,
    scenario_manifest_writer: Callable[[Any], Path] | None = None,
    catalog: PluginCatalog | None = None,
    run_competence_preflight: bool = True,
) -> ExecutionResult:
    """Execute a normalized plan with the canonical coordinator and ordering."""

    catalog = catalog or plan.planner.catalog
    planned_order = tuple(item.episode_id for item in plan.episodes)
    existing = _unique_episodes(existing_episodes, planned_order=planned_order)
    existing_ids = {episode.episode_id for episode in existing}
    planned_ids = {item.episode_id for item in plan.episodes}
    unknown = existing_ids - planned_ids
    if unknown:
        from tool_agent_shift_benchmark.core.orchestration import UnknownEpisodeSelectionError

        raise UnknownEpisodeSelectionError("existing", unknown)
    competence_report = run_clean_competence_preflight(plan.spec, catalog) if run_competence_preflight else {}
    coordinator = RunCoordinator(plan.spec, catalog)
    produced = coordinator.run(
        existing_ids,
        checkpoint_path=checkpoint_path,
        scenario_manifest_dir=scenario_manifest_dir,
        scenario_manifest_writer=scenario_manifest_writer,
    )
    episodes = _unique_episodes((*existing, *produced), planned_order=planned_order)
    return ExecutionResult(
        plan=plan,
        episodes=episodes,
        orchestration_errors=tuple(error.to_dict() for error in coordinator.errors),
        competence_report=competence_report,
        scenario_specs=coordinator.scenario_specs,
    )
