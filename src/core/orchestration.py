"""Deterministic planning and episode orchestration."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any

from src.core.catalog import PluginCatalog
from src.core.context import ObservationContext, redact_response_for_policy
from src.core.contracts import OrchestrationError
from src.core.episode import Episode
from src.core.evaluator import HiddenStateEvaluator
from src.core.types import (
    AgentAction,
    AgentDecision,
    FaultConfig,
    MonitorDecision,
    stable_hash,
)
from src.monitors.composite import CompositeMonitor

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
    episodes_per_combo: int = 1
    episode_steps: int = 1
    workers: int = 1
    monitor_policy: str = "gate"
    failure_policy: str = "continue"
    retry_attempts: int = 0
    monitor: str = "composite"
    artifact_policy: str = "bundle"
    scenario_indices: tuple[int, ...] = ()
    episode_ids: tuple[str, ...] = ()
    selection_offset: int = 0
    selection_limit: int | None = None
    partition_index: int | None = None
    partition_count: int | None = None
    replay_episode_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
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
    def from_config(cls, config: dict[str, Any], seed: int = 42, **overrides: Any) -> "ExperimentSpec":
        raw_shifts = tuple(str(x) for x in (config.get("faults") or ("normal",)))
        raw_chains = config.get("shift_chains")
        chains = (
            tuple(tuple(str(x) for x in chain) for chain in raw_chains)
            if raw_chains
            else tuple((x,) for x in raw_shifts)
        )
        return cls(
            config=dict(config),
            seed=seed,
            environments=tuple(overrides.get("environments") or config.get("environments") or ("file_ops",)),
            agents=tuple(overrides.get("agents") or config.get("agents") or ("naive",)),
            shifts=raw_shifts,
            shift_chains=chains,
            severities=tuple(float(x) for x in config.get("fault_severities", (1.0,))),
            episodes_per_combo=int(config.get("episodes_per_combo", 3)),
            episode_steps=int(config.get("episode_steps", 1)),
            workers=int(overrides.get("workers", config.get("workers", 1))),
            monitor_policy=str(config.get("monitor_policy", "gate")),
            failure_policy=str(config.get("failure_policy", "continue")),
            retry_attempts=int(config.get("retry_attempts", 0)),
            monitor=str(config.get("monitor", "composite")),
            artifact_policy=str(config.get("artifact_policy", "bundle")),
            scenario_indices=tuple(
                int(x) for x in (overrides.get("scenario_indices") or config.get("scenario_indices") or ())
            ),
            episode_ids=tuple(str(x) for x in (overrides.get("episode_ids") or config.get("episode_ids") or ())),
            selection_offset=int(overrides.get("selection_offset", config.get("selection_offset", 0))),
            selection_limit=(
                int(value)
                if (value := overrides.get("selection_limit", config.get("selection_limit"))) is not None
                else None
            ),
            partition_index=(
                int(value)
                if (value := overrides.get("partition_index", config.get("partition_index"))) is not None
                else None
            ),
            partition_count=(
                int(value)
                if (value := overrides.get("partition_count", config.get("partition_count"))) is not None
                else None
            ),
            replay_episode_ids=tuple(
                str(x) for x in (overrides.get("replay_episode_ids") or config.get("replay_episode_ids") or ())
            ),
        )

    def identity_config_v1(self) -> dict[str, Any]:
        """Return the legacy hash input with operational selectors removed.

        Keeping the remaining shape unchanged preserves IDs from complete,
        unfiltered legacy plans while making all selection a post-ID operation.
        Identity v2 replaces this compatibility helper in Checkpoint 6.
        """

        return {key: value for key, value in self.config.items() if key not in OPERATIONAL_SELECTOR_KEYS}

    def digest(self) -> str:
        return str(stable_hash(self.config, prefix="cfg"))


@dataclass(frozen=True)
class EpisodeSpec:
    run_id: str
    environment: str
    agent: str
    shift: str
    severity: float
    scenario_index: int
    seed: int
    episode_id: str


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
            }
        )
        self.run_id = stable_hash(
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

    def canonical_plan(self) -> list[EpisodeSpec]:
        """Construct every semantic episode before applying selectors."""

        planned: list[EpisodeSpec] = []
        for env in self.spec.environments:
            for agent in self.spec.agents:
                for chain in self.spec.shift_chains:
                    shift = "+".join(chain)
                    for severity in self.spec.severities:
                        if shift == "normal" and severity != 1.0:
                            continue
                        for index in range(self.spec.episodes_per_combo):
                            scenario_id = f"{env}_scenario_{index}"
                            identity = {
                                "run": self.run_id,
                                "environment": env,
                                "agent": agent,
                                "shift": shift,
                                "severity": severity,
                                "scenario_index": index,
                                "scenario": scenario_id,
                            }
                            seed = int(
                                stable_hash({"seed": self.spec.seed, **identity}, prefix="seed").split("_")[1],
                                16,
                            ) % (2**31)
                            episode_id = stable_hash(
                                {
                                    "env": env,
                                    "scenario": scenario_id,
                                    "agent": agent,
                                    "fault": shift,
                                    "severity": severity,
                                    "seed": seed,
                                    "run_id": self.run_id,
                                },
                                prefix="ep",
                            )
                            item = EpisodeSpec(
                                self.run_id,
                                env,
                                agent,
                                shift,
                                severity,
                                index,
                                seed,
                                episode_id,
                            )
                            planned.append(item)
        return planned

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
        if self.spec.partition_count is not None:
            selected = [
                item
                for position, item in enumerate(selected)
                if position % self.spec.partition_count == self.spec.partition_index
            ]
        start = self.spec.selection_offset
        stop = None if self.spec.selection_limit is None else start + self.spec.selection_limit
        return selected[start:stop]


class EpisodeRunner:
    def __init__(self, spec: ExperimentSpec, catalog: PluginCatalog | None = None):
        self.spec, self.catalog = spec, catalog or PluginCatalog()

    def run(self, item: EpisodeSpec) -> Episode:
        env_obj = self.catalog.get("environment", item.environment)(seed=item.seed, scenario_index=item.scenario_index)
        agent_obj = self.catalog.get("agent", item.agent)()
        shift_objs = [self.catalog.get("shift", name)(severity=item.severity) for name in item.shift.split("+")]
        evaluator = HiddenStateEvaluator()
        monitor_factory = self.catalog.get("monitor", self.spec.monitor)
        monitor = monitor_factory() if self.spec.monitor != "composite" else CompositeMonitor()
        monitors: list[MonitorDecision] = []
        step_trace: list[dict[str, Any]] = []
        evaluator_trace: list[dict[str, Any]] = []
        final_response = final_decision = final_execution = None
        stop_reason, failure_step, unsafe_steps = "max_steps", "", 0
        for step in range(self.spec.episode_steps):
            clean = env_obj.tool_response()
            step_seed = int(
                stable_hash({"episode": item.episode_id, "step": step}, prefix="step").split("_")[1],
                16,
            ) % (2**31)
            shifted = clean
            for shift_index, shift_obj in enumerate(shift_objs):
                shift_rng_seed = int(
                    stable_hash(
                        {"step_seed": step_seed, "shift_index": shift_index},
                        prefix="shift",
                    ).split("_")[1],
                    16,
                ) % (2**31)
                shifted = shift_obj.apply(shifted, env_obj, Random(shift_rng_seed))
            policy_response = redact_response_for_policy(shifted)
            context = ObservationContext.from_environment(env_obj, policy_response.observation)
            decision = agent_obj.decide(context, policy_response)
            monitor_decision = (
                getattr(agent_obj, "last_monitor_decision", None) if item.agent == "monitor_gated" else None
            )
            monitor_decision = monitor_decision or monitor.check(context, policy_response.observation, decision.action)
            monitors.append(monitor_decision)
            action = decision.action
            if self.spec.monitor_policy == "gate" and not monitor_decision.allow_action and not action.abstain:
                action = AgentAction("abstain", abstain=True, reason="monitor_blocked")
                decision = AgentDecision(
                    decision.agent_name,
                    action,
                    decision.confidence,
                    list(decision.reasons),
                    {**decision.metadata, "monitor_gated": True},
                )
            execution = env_obj.execute(action, observed_timestamp=policy_response.observation.timestamp)
            if execution.unsafe:
                unsafe_steps += 1
                failure_step = failure_step or str(step)
                stop_reason = "unsafe_action"
            elif action.abstain:
                stop_reason = "abstained"
            elif execution.success:
                stop_reason = "success"
            step_trace.append(
                {
                    "step": step,
                    "tool_response": policy_response.to_dict(),
                    "decision": decision.to_dict(),
                    "monitor": monitor_decision.to_dict(),
                    "execution": execution.to_dict(),
                }
            )
            score = evaluator.score(env_obj, action, execution)
            evaluator_trace.append(
                {
                    "step": step,
                    "shift_provenance": shifted.observation.metadata.get("faults", []),
                    **score,
                }
            )
            final_response, final_decision, final_execution = (
                shifted,
                decision,
                execution,
            )
            if execution.unsafe or action.abstain or execution.success:
                break
        recovered = bool(
            item.shift != "normal"
            and final_execution
            and not final_execution.unsafe
            and final_decision is not None
            and (final_decision.action.abstain or any(not m.allow_action for m in monitors))
        )
        metadata = {
            "config_path": self.spec.config.get("_config_path", ""),
            "combo_seed": item.seed,
            "episode_steps": self.spec.episode_steps,
            "steps_taken": len(step_trace),
            "multi_step": self.spec.episode_steps > 1,
            "unsafe_step_count": unsafe_steps,
            "failure_step": failure_step,
            "stop_reason": stop_reason,
            "step_trace": step_trace,
            "evaluator_trace": evaluator_trace,
            "recovered": recovered,
        }
        return Episode(
            item.environment,
            env_obj.scenario_id,
            item.agent,
            FaultConfig(item.shift, item.severity),
            item.seed,
            item.run_id,
            final_response,
            final_decision,
            monitors,
            final_execution,
            metadata,
        )


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
                if attempt <= self.retry_attempts:
                    continue
                error = OrchestrationError(item.episode_id, "episode", type(exc).__name__, str(exc), attempt)
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

    def run(
        self,
        completed: set[str] | None = None,
        checkpoint_path: str | Path | None = None,
    ) -> list[Episode]:
        planner = ExperimentPlanner(self.spec, self.catalog)
        self.run_id = planner.run_id
        scheduler = EpisodeScheduler(
            EpisodeRunner(self.spec, self.catalog),
            self.spec.workers,
            self.spec.retry_attempts,
            self.spec.failure_policy,
        )
        if checkpoint_path and Path(checkpoint_path).exists():
            saved = json.loads(Path(checkpoint_path).read_text(encoding="utf-8"))
            completed = set(completed or set()) | set(saved.get("completed_episode_ids", []))
        canonical_ids = {item.episode_id for item in planner.canonical_plan()}
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
                path.write_text(
                    json.dumps(
                        {
                            "run_id": planner.run_id,
                            "completed_episode_ids": sorted(completed or set()),
                            "errors": [e.to_dict() for e in self.errors],
                        },
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
            raise
        self.errors = sorted(scheduler.errors, key=lambda error: error.episode_id)
        if checkpoint_path:
            path = Path(checkpoint_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "run_id": planner.run_id,
                        "completed_episode_ids": sorted((completed or set()) | {e.episode_id for e in episodes}),
                        "errors": [e.to_dict() for e in self.errors],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        return sorted(episodes, key=lambda e: e.episode_id)
