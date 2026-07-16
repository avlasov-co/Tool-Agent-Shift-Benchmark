from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from src.agents import AGENTS
from src.core.config import load_config
from src.core.episode import Episode
from src.core.orchestration import ExperimentSpec, RunCoordinator
from src.core.serialization import canonical_dumps, write_csv, write_json, write_jsonl
from src.environments.calendar_ops import CalendarOpsEnvironment
from src.environments.file_ops import FileOpsEnvironment
from src.environments.risk_ops import RiskOpsEnvironment
from src.metrics.aggregation import aggregate

ENVS = {
    "file_ops": FileOpsEnvironment,
    "calendar_ops": CalendarOpsEnvironment,
    "risk_ops": RiskOpsEnvironment,
}


def _safe_summary(value):
    if isinstance(value, list):
        return f"list[{len(value)}]"
    if isinstance(value, dict):
        return {k: _safe_summary(v) for k, v in list(value.items())[:6]}
    return value


def _static_dynamic_rows(episodes: List[Episode]):
    by_agent = {}
    for e in episodes:
        by_agent.setdefault(e.agent_name, []).append(e)
    rows = []
    for agent, eps in sorted(by_agent.items()):
        clean = [e for e in eps if e.fault.name == "normal"]
        shifted = [e for e in eps if e.fault.name != "normal"]
        static = sum(e.execution.success and not e.execution.unsafe for e in clean) / len(clean) if clean else 0.0
        dynamic = (
            sum(e.execution.success and not e.execution.unsafe and not e.decision.action.abstain for e in shifted)
            / len(shifted)
            if shifted
            else 0.0
        )
        rows.append(
            {
                "agent_name": agent,
                "static_score": static,
                "dynamic_score": dynamic,
                "gap": static - dynamic,
                "clean_episodes": len(clean),
                "shifted_episodes": len(shifted),
            }
        )
    return rows


def run_eval(
    config_path: str,
    seed: int | None,
    env: str | None = None,
    agent: str | None = None,
    all_envs: bool = False,
    all_agents: bool = False,
    workers: int | None = None,
    existing_episodes: List[Episode] | None = None,
    checkpoint_path: str | None = None,
    scenario_indices=None,
    episode_ids=None,
    selection_offset: int | None = None,
    selection_limit: int | None = None,
    partition_index: int | None = None,
    partition_count: int | None = None,
    replay_episode_ids=None,
) -> List[Episode]:
    source_config = load_config(config_path)
    env_names = list(ENVS) if all_envs else ([env] if env else source_config.get("environments", ["file_ops"]))
    agent_names = list(AGENTS) if all_agents else ([agent] if agent else source_config.get("agents", ["naive"]))
    selected_config = {
        **source_config,
        "environments": env_names,
        "agents": agent_names,
    }
    runtime_config = {
        **selected_config,
        "_config_path": config_path,
        "_working_directory": str(Path.cwd()),
    }
    spec = ExperimentSpec.from_config(
        runtime_config,
        seed=seed,
        environments=env_names,
        agents=agent_names,
        workers=workers,
        scenario_indices=scenario_indices,
        episode_ids=episode_ids,
        selection_offset=selection_offset,
        selection_limit=selection_limit,
        partition_index=partition_index,
        partition_count=partition_count,
        replay_episode_ids=replay_episode_ids,
    )
    coordinator = RunCoordinator(spec)
    normalized_config = {
        **source_config,
        "environments": list(spec.environments),
        "agents": list(spec.agents),
        "seed": spec.seed,
        "workers": spec.workers,
        "scenario_indices": list(spec.scenario_indices),
        "episode_ids": list(spec.episode_ids),
        "selection_offset": spec.selection_offset,
        "selection_limit": spec.selection_limit,
        "partition_index": spec.partition_index,
        "partition_count": spec.partition_count,
        "replay_episode_ids": list(spec.replay_episode_ids),
    }
    existing_episodes = existing_episodes or []
    episodes = coordinator.run({e.episode_id for e in existing_episodes}, checkpoint_path=checkpoint_path)
    episodes = sorted(existing_episodes + episodes, key=lambda e: e.episode_id)
    run_id = episodes[0].run_id if episodes else coordinator.run_id
    if run_id is None:
        raise RuntimeError("planner did not provide a run ID")
    if coordinator.identity is None:
        raise RuntimeError("planner did not provide an identity document")
    effective_config = {
        "source_config_path": config_path,
        "all_envs": all_envs,
        "all_agents": all_agents,
        "requested_env": env,
        "requested_agent": agent,
        "workers": spec.workers,
        "scenario_indices": list(spec.scenario_indices),
        "episode_ids": list(spec.episode_ids),
        "selection_offset": spec.selection_offset,
        "selection_limit": spec.selection_limit,
        "partition_index": spec.partition_index,
        "partition_count": spec.partition_count,
        "replay_episode_ids": list(spec.replay_episode_ids),
    }
    write_outputs(
        episodes,
        normalized_config,
        spec.seed,
        run_id,
        identity=coordinator.identity.to_dict(),
        config_digest=coordinator.identity.config_digest,
        operational_request=effective_config,
        orchestration_errors=[e.to_dict() for e in coordinator.errors],
    )
    return episodes


def write_outputs(
    episodes: List[Episode],
    config,
    seed: int,
    run_id: str,
    identity=None,
    config_digest: str | None = None,
    operational_request=None,
    orchestration_errors=None,
) -> None:
    Path("results").mkdir(exist_ok=True)
    # A single-seed run invalidates previous multi-seed artifacts. Leaving stale
    # confidence intervals beside a fresh summary is how toy repos cosplay as
    # research artifacts. Delete them and let run_seeds recreate them explicitly.
    for stale in ["results/seed_summary.csv", "results/confidence_intervals.csv"]:
        Path(stale).unlink(missing_ok=True)
    write_csv("results/episode_log.csv", [e.to_row() for e in episodes])
    write_csv("results/summary.csv", aggregate(episodes))
    write_csv("results/static_vs_dynamic.csv", _static_dynamic_rows(episodes))
    write_jsonl(
        "results/multistep_traces.jsonl",
        (
            {"episode_id": episode.episode_id, "step_trace": episode.metadata.get("step_trace", [])}
            for episode in episodes
        ),
    )
    write_jsonl(
        "results/episodes.jsonl", (episode.to_dict() for episode in sorted(episodes, key=lambda e: e.episode_id))
    )
    write_jsonl(
        "results/evaluator_traces.jsonl",
        (
            {"episode_id": episode.episode_id, "trace": episode.metadata.get("evaluator_trace", [])}
            for episode in episodes
        ),
    )
    errors = orchestration_errors or []
    write_jsonl("results/orchestration_errors.jsonl", errors or [{"orchestration_errors": []}])
    failure_rows = []
    for e in episodes:
        if e.execution.unsafe:
            fc = e.failure_case()
            monitor_summary = ";".join(r for m in e.monitor_decisions for r in m.reasons)
            failure_rows.append(
                {
                    "case_id": fc.case_id,
                    "episode_id": fc.episode_id,
                    "env_name": fc.env_name,
                    "environment": fc.env_name,
                    "agent_name": fc.agent_name,
                    "agent": fc.agent_name,
                    "fault_name": fc.fault_name,
                    "fault": fc.fault_name,
                    "action_type": e.decision.action.action_type,
                    "unsafe_reasons": ";".join(fc.unsafe_reasons),
                    "observation_summary": canonical_dumps(_safe_summary(e.tool_response.observation.data)),
                    "monitor_summary": monitor_summary,
                    "ground_truth_summary": canonical_dumps(
                        _safe_summary((e.metadata.get("evaluator_trace") or [{}])[-1].get("hidden_ground_truth", {}))
                    ),
                    "seed": fc.seed,
                    "trace_json": canonical_dumps(fc.trace),
                }
            )
    write_csv(
        "results/failure_cases.csv",
        failure_rows,
        [
            "case_id",
            "episode_id",
            "env_name",
            "environment",
            "agent_name",
            "agent",
            "fault_name",
            "fault",
            "action_type",
            "unsafe_reasons",
            "observation_summary",
            "monitor_summary",
            "ground_truth_summary",
            "seed",
            "trace_json",
        ],
    )
    monitor_rows = []
    for e in episodes:
        for m in e.monitor_decisions:
            monitor_rows.append(
                {
                    "episode_id": e.episode_id,
                    "env_name": e.env_name,
                    "agent_name": e.agent_name,
                    "fault_name": e.fault.name,
                    "monitor_name": m.monitor_name,
                    "allow_action": m.allow_action,
                    "risk_score": m.risk_score,
                    "reasons": ";".join(m.reasons),
                    "metadata_json": canonical_dumps(m.metadata),
                }
            )
    write_csv("results/monitor_events.csv", monitor_rows)
    write_json(
        "results/config.json",
        {
            "seed": seed,
            "run_id": run_id,
            "config_digest": config_digest,
            "identity": identity,
            "config": config,
            "normalized_config": config,
            "operational_request": operational_request or {},
            "episodes": len(episodes),
            "orchestration_errors": orchestration_errors or [],
        },
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Tool-Agent Shift Benchmark")
    parser.add_argument("--config", default="configs/small.yaml")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--env", choices=list(ENVS))
    parser.add_argument("--agent", choices=list(AGENTS))
    parser.add_argument("--all-envs", action="store_true")
    parser.add_argument("--all-agents", action="store_true")
    args = parser.parse_args(argv)
    episodes = run_eval(
        args.config,
        args.seed,
        env=args.env,
        agent=args.agent,
        all_envs=args.all_envs,
        all_agents=args.all_agents,
    )
    print(f"wrote results for {len(episodes)} episodes")


if __name__ == "__main__":
    main()
