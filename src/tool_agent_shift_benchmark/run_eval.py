from __future__ import annotations

import argparse
from typing import Callable, List

from tool_agent_shift_benchmark.agents import AGENTS
from tool_agent_shift_benchmark.core.action_records import ACTION_RECORD_CONTRACT, EPISODE_RECORD_VERSION
from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.counterfactual import COUNTERFACTUAL_EVALUATION_CONTRACT
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.execution import (
    ExecutionRequest,
    execute_plan,
    normalize_execution_request,
)
from tool_agent_shift_benchmark.core.run_artifacts import prepare_run_dir
from tool_agent_shift_benchmark.core.scenarios import (
    SCENARIO_COVERAGE_CONTRACT,
    SCENARIO_FAMILY_CONTRACT,
    SCENARIO_MANIFEST_CONTRACT,
    SCENARIO_SPLIT_CONTRACT,
    ScenarioSpec,
    scenario_coverage_rows,
    scenario_coverage_summary,
)
from tool_agent_shift_benchmark.core.serialization import canonical_dumps
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment
from tool_agent_shift_benchmark.metrics.aggregation import aggregate, metric_evidence, within_scenario_deltas
from tool_agent_shift_benchmark.metrics.monitor_evaluation import MONITOR_EVALUATION_SCHEMA_VERSION
from tool_agent_shift_benchmark.metrics.outcomes import METRIC_SCHEMA_VERSION, classify_episode

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


def _clean_shifted_rows(episodes: List[Episode]):
    by_agent = {}
    for e in episodes:
        by_agent.setdefault(e.agent_name, []).append(e)
    rows = []
    for agent, eps in sorted(by_agent.items()):
        clean = [e for e in eps if e.fault.name == "normal"]
        shifted = [e for e in eps if e.fault.name != "normal"]
        clean_rate = sum(e.execution.success and not e.execution.unsafe for e in clean) / len(clean) if clean else 0.0
        shifted_rate = (
            sum(e.execution.success and not e.execution.unsafe for e in shifted) / len(shifted) if shifted else 0.0
        )
        rows.append(
            {
                "agent_name": agent,
                "clean_safe_success_rate": clean_rate,
                "shifted_safe_success_rate": shifted_rate,
                "safe_success_gap": clean_rate - shifted_rate,
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
    monitor_modes=None,
    oversight_modes=None,
    artifact_store: ArtifactStore | None = None,
    failure_injector: Callable[[str], None] | None = None,
) -> List[Episode]:
    request = ExecutionRequest(
        config_path=config_path,
        mode="replay" if replay_episode_ids else "ordinary",
        seed=seed,
        environments=(env,) if env else (),
        agents=(agent,) if agent else (),
        all_environments=all_envs,
        all_agents=all_agents,
        workers=workers,
        scenario_indices=tuple(scenario_indices or ()),
        episode_ids=tuple(episode_ids or ()),
        selection_offset=selection_offset,
        selection_limit=selection_limit,
        partition_index=partition_index,
        partition_count=partition_count,
        replay_episode_ids=tuple(replay_episode_ids or ()),
        monitor_modes=tuple(monitor_modes or ()),
        oversight_modes=tuple(oversight_modes or ()),
    )
    plan = normalize_execution_request(request)
    implicit_bundle = artifact_store is None
    if artifact_store is None:
        artifact_store = ArtifactStore(prepare_run_dir())
    spec = plan.spec
    normalized_config = {
        **{key: value for key, value in plan.normalized_config.items() if not key.startswith("_")},
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
        "monitor_modes": list(spec.monitor_modes),
        "oversight_modes": list(spec.oversight_modes),
    }
    effective_config = {
        **request.to_dict(),
        "execution_plan_schema_version": plan.to_dict()["schema_version"],
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
    planned_count = len(plan.episodes)
    existing_by_id = {episode.episode_id: episode for episode in existing_episodes or ()}
    traced_episode_ids = set(existing_by_id)

    def _status_payload(completed_ids: set[str], failed_ids: set[str], pending_ids: set[str]) -> dict[str, int | str]:
        return {
            "schema_version": "run-status-v1",
            "planned_episodes": planned_count,
            "started_episodes": len(completed_ids | failed_ids),
            "completed_episodes": len(completed_ids),
            "failed_episodes": len(failed_ids),
            "skipped_episodes": 0,
            "pending_episodes": len(pending_ids),
            "invalid_episodes": 0,
        }

    # Persist enough of the bundle before execution for a crash before the
    # first episode to remain inspectable and safely resumable.
    artifact_store.write_json("config/normalized_config.json", normalized_config)
    artifact_store.write_json("identity/experiment_identity.json", plan.planner.identity.to_dict())
    artifact_store.write_json(
        "plugins/descriptors.json",
        {"schema_version": "plugin-descriptors-v2", "descriptors": plan.planner.catalog.as_dict()},
    )
    artifact_store.write_json("plan/execution_plan.json", plan.to_dict())
    artifact_store.write_json(
        "results/config.json",
        {
            "artifact_schema_version": "run-results-v2",
            "run_id": plan.planner.run_id,
            "config_digest": plan.planner.identity.config_digest,
            "identity": plan.planner.identity.to_dict(),
            "config": normalized_config,
            "normalized_config": normalized_config,
            "operational_request": effective_config,
            "planned_episodes": planned_count,
            "completed_episodes": len(existing_by_id),
            "failed_episodes": 0,
        },
    )
    artifact_store.write_json(
        "status.json",
        _status_payload(set(existing_by_id), set(), {item.episode_id for item in plan.episodes} - set(existing_by_id)),
    )

    def _write_progress(
        produced: tuple[Episode, ...],
        errors: tuple[dict[str, object], ...],
        completed_ids: set[str],
        failed_ids: set[str],
        pending_ids: set[str],
    ) -> None:
        for episode in produced:
            existing = existing_by_id.get(episode.episode_id)
            if existing is not None and existing.to_dict() != episode.to_dict():
                raise ValueError(f"duplicate episode ID has divergent records: {episode.episode_id}")
            existing_by_id[episode.episode_id] = episode
        episodes_to_persist = [existing_by_id[episode_id] for episode_id in sorted(existing_by_id)]
        # A trace is durable before its episode row becomes a resume-complete
        # record. If the trace write fails, the checkpoint cannot advance.
        for episode in episodes_to_persist:
            if episode.episode_id in traced_episode_ids:
                continue
            artifact_store.write_trace(
                episode.episode_id,
                policy={"episode_id": episode.episode_id, "step_trace": episode.metadata.get("step_trace", [])},
                evaluator={
                    "episode_id": episode.episode_id,
                    "trace": episode.metadata.get("evaluator_trace", []),
                    "action_records": [record.to_dict() for record in episode.action_records],
                },
                failure_injector=failure_injector,
            )
            traced_episode_ids.add(episode.episode_id)
        artifact_store.write_jsonl("results/episodes.jsonl", (episode.to_dict() for episode in episodes_to_persist))
        artifact_store.write_jsonl("results/orchestration_errors.jsonl", errors or ({"orchestration_errors": []},))
        artifact_store.write_json("status.json", _status_payload(completed_ids, failed_ids, pending_ids))
        if failure_injector is not None:
            failure_injector("after_status_write")

    result = execute_plan(
        plan,
        existing_episodes=existing_episodes or (),
        checkpoint_path=checkpoint_path,
        scenario_manifest_writer=artifact_store.write_scenario_manifest,
        # A caller that does not request a checkpoint has no resume target; it
        # retains the compatibility final-write behavior. CLI and resumable
        # runs always provide a bundle-local checkpoint path.
        progress_writer=_write_progress if checkpoint_path is not None else None,
        failure_injector=failure_injector,
    )
    write_outputs(
        artifact_store,
        list(result.episodes),
        normalized_config,
        spec.seed,
        plan.planner.run_id,
        identity=plan.planner.identity.to_dict(),
        config_digest=plan.planner.identity.config_digest,
        operational_request=effective_config,
        orchestration_errors=list(result.orchestration_errors),
        competence_report=result.competence_report,
        scenario_specs=result.scenario_specs,
        plugin_catalog=plan.planner.catalog.as_dict(),
    )
    artifact_store.write_json("plan/execution_plan.json", plan.to_dict())
    if failure_injector is not None:
        failure_injector("before_finalization")
    if implicit_bundle:
        artifact_store.finalize(command=["run_eval", "compatibility-wrapper"])
    return list(result.episodes)


def write_outputs(
    store: ArtifactStore,
    episodes: List[Episode],
    config,
    seed: int,
    run_id: str,
    identity=None,
    config_digest: str | None = None,
    operational_request=None,
    orchestration_errors=None,
    competence_report=None,
    scenario_specs: tuple[ScenarioSpec, ...] = (),
    plugin_catalog: list[dict[str, object]] | None = None,
) -> None:
    errors = list(orchestration_errors or [])
    store.write_csv("results/episode_log.csv", [e.to_row() for e in episodes])
    store.write_csv("results/summary.csv", aggregate(episodes, errors))
    metric_rows = metric_evidence(episodes, errors)
    store.write_csv("results/metric_evidence.csv", metric_rows)
    store.write_jsonl("results/metric_evidence.jsonl", metric_rows)
    episode_outcome_rows = []
    step_outcome_rows = []
    for episode in episodes:
        outcome = classify_episode(episode)
        outcome_row = outcome.to_dict()
        steps = outcome_row.pop("steps")
        scenario_manifest = episode.metadata.get("scenario_manifest") or {}
        scenario_family = scenario_manifest.get("family") or {}
        seed_streams = episode.metadata.get("seed_streams") or {}
        hierarchy = {
            "scenario_family": scenario_family.get("name", "unknown"),
            "scenario_split": scenario_manifest.get("split", "unknown"),
            "scenario_seed": scenario_manifest.get("scenario_seed", episode.seed),
            "root_seed": seed_streams.get("root_seed", seed),
            "monitor_mode": episode.metadata.get("monitor_mode", "full_composite_monitor"),
            "oversight_mode": episode.metadata.get("oversight_mode", "hard_gate"),
        }
        episode_outcome_rows.append(
            {
                "metric_schema_version": METRIC_SCHEMA_VERSION,
                "run_id": episode.run_id,
                "episode_id": episode.episode_id,
                "scenario_pair_id": episode.scenario_pair_id or "",
                "scenario_manifest_hash": scenario_manifest.get("content_hash", ""),
                "environment": episode.env_name,
                "agent": episode.agent_name,
                "fault": episode.fault.name,
                "severity": episode.fault.severity,
                **hierarchy,
                **outcome_row,
            }
        )
        for step in steps:
            step_outcome_rows.append(
                {
                    "metric_schema_version": METRIC_SCHEMA_VERSION,
                    "run_id": episode.run_id,
                    "episode_id": episode.episode_id,
                    "scenario_pair_id": episode.scenario_pair_id or "",
                    "scenario_manifest_hash": scenario_manifest.get("content_hash", ""),
                    "environment": episode.env_name,
                    "agent": episode.agent_name,
                    "fault": episode.fault.name,
                    "severity": episode.fault.severity,
                    **hierarchy,
                    **step,
                }
            )
    store.write_csv("results/episode_outcomes.csv", episode_outcome_rows)
    store.write_jsonl("results/episode_outcomes.jsonl", episode_outcome_rows)
    store.write_csv("results/step_outcomes.csv", step_outcome_rows)
    store.write_jsonl("results/step_outcomes.jsonl", step_outcome_rows)
    store.write_csv("results/clean_vs_shifted.csv", _clean_shifted_rows(episodes))
    store.write_csv("results/within_scenario_deltas.csv", within_scenario_deltas(episodes))
    coverage = scenario_coverage_summary(scenario_specs)
    store.write_json("results/scenario_coverage.json", coverage)
    store.write_csv("results/scenario_coverage.csv", scenario_coverage_rows(coverage))
    store.write_jsonl(
        "results/multistep_traces.jsonl",
        (
            {"episode_id": episode.episode_id, "step_trace": episode.metadata.get("step_trace", [])}
            for episode in episodes
        ),
    )
    store.write_jsonl(
        "results/episodes.jsonl", (episode.to_dict() for episode in sorted(episodes, key=lambda e: e.episode_id))
    )
    action_record_rows = []
    for episode in episodes:
        for record in episode.action_records:
            counterfactual = record.evaluator_labels.get("counterfactual", {})
            proposed_score = counterfactual.get("proposed_action", {})
            executed_score = counterfactual.get("executed_action", {})
            realized_score = counterfactual.get("realized_outcome", {})
            action_record_rows.append(
                {
                    "episode_id": episode.episode_id,
                    "agent_name": episode.agent_name,
                    "environment": episode.env_name,
                    "fault": episode.fault.name,
                    "oversight_mode": episode.metadata.get("oversight_mode", "hard_gate"),
                    "monitor_mode": episode.metadata.get("monitor_mode", "full_composite_monitor"),
                    "sequence": record.sequence,
                    "status": record.status,
                    "proposed_action_type": record.proposed_action.action_type if record.proposed_action else "",
                    "proposed_target": (record.proposed_action.target if record.proposed_action else None) or "",
                    "executed_action_type": record.executed_action.action_type if record.executed_action else "",
                    "executed_target": (record.executed_action.target if record.executed_action else None) or "",
                    "intervention_type": record.intervention.intervention_type if record.intervention else "",
                    "monitor_name": record.monitor_decision.monitor_name if record.monitor_decision else "",
                    "monitor_allow_action": record.monitor_decision.allow_action if record.monitor_decision else "",
                    "proposed_action_unsafe": proposed_score.get("unsafe", ""),
                    "proposed_action_success": proposed_score.get("success", ""),
                    "executed_action_unsafe": executed_score.get("unsafe", ""),
                    "realized_unsafe": realized_score.get("unsafe", ""),
                    "proposed_action_risk_label": counterfactual.get("proposed_action_risk_label", ""),
                    "intervention_effect": counterfactual.get("intervention_effect", ""),
                    "execution_equivalent": counterfactual.get("execution_equivalent", ""),
                    "execution_success": record.execution_result.success if record.execution_result else "",
                    "execution_unsafe": record.execution_result.unsafe if record.execution_result else "",
                    "stop_reason": record.stop_reason,
                    "policy_explanation_json": canonical_dumps(
                        record.policy_explanation.to_dict() if record.policy_explanation else {}
                    ),
                    "intervention_json": canonical_dumps(record.intervention.to_dict() if record.intervention else {}),
                    "execution_result_json": canonical_dumps(
                        record.execution_result.to_dict() if record.execution_result else {}
                    ),
                    "counterfactual_json": canonical_dumps(counterfactual),
                    "evaluator_labels_json": canonical_dumps(record.evaluator_labels),
                }
            )
    store.write_csv("results/action_records.csv", action_record_rows)
    store.write_jsonl(
        "results/action_records.jsonl",
        (
            {"episode_id": episode.episode_id, "action_record": record.to_dict()}
            for episode in episodes
            for record in episode.action_records
        ),
    )
    store.write_jsonl(
        "results/evaluator_traces.jsonl",
        (
            {
                "episode_id": episode.episode_id,
                "trace": episode.metadata.get("evaluator_trace", []),
                "action_records": [record.to_dict() for record in episode.action_records],
            }
            for episode in episodes
        ),
    )
    store.write_jsonl("results/orchestration_errors.jsonl", errors or [{"orchestration_errors": []}])
    competence = competence_report or {
        "schema_version": "1",
        "passed": False,
        "failed_gates": ["competence_preflight_not_run"],
        "rows": [],
    }
    store.write_json("results/competence_report.json", competence)
    failure_rows = []
    for e in episodes:
        if e.execution.unsafe:
            fc = e.failure_case()
            final_record = e.action_records[-1]
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
                    "action_type": final_record.executed_action.action_type,
                    "proposed_action_type": final_record.proposed_action.action_type,
                    "executed_action_type": final_record.executed_action.action_type,
                    "intervention_type": final_record.intervention.intervention_type,
                    "stop_reason": final_record.stop_reason,
                    "evaluator_labels_json": canonical_dumps(final_record.evaluator_labels),
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
    store.write_csv(
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
            "proposed_action_type",
            "executed_action_type",
            "intervention_type",
            "stop_reason",
            "evaluator_labels_json",
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
        scenario_manifest = e.metadata.get("scenario_manifest") or {}
        scenario_family = scenario_manifest.get("family") or {}
        seed_streams = e.metadata.get("seed_streams") or {}
        for sequence, m in enumerate(e.monitor_decisions):
            record = e.action_records[sequence] if sequence < len(e.action_records) else None
            counterfactual = record.evaluator_labels.get("counterfactual", {}) if record else {}
            proposed_score = counterfactual.get("proposed_action", {})
            executed_score = counterfactual.get("executed_action", {})
            realized_score = counterfactual.get("realized_outcome", {})
            monitor_rows.append(
                {
                    "monitor_evaluation_schema_version": MONITOR_EVALUATION_SCHEMA_VERSION,
                    "episode_id": e.episode_id,
                    "env_name": e.env_name,
                    "environment": e.env_name,
                    "agent_name": e.agent_name,
                    "agent": e.agent_name,
                    "fault_name": e.fault.name,
                    "fault": e.fault.name,
                    "severity": e.fault.severity,
                    "scenario_manifest_hash": scenario_manifest.get("content_hash", ""),
                    "scenario_family": scenario_family.get("name", "unknown"),
                    "scenario_split": scenario_manifest.get("split", "unknown"),
                    "root_seed": seed_streams.get("root_seed", seed),
                    "monitor_mode": e.metadata.get("monitor_mode", "full_composite_monitor"),
                    "oversight_mode": e.metadata.get("oversight_mode", "hard_gate"),
                    "monitor_name": m.monitor_name,
                    "sequence": sequence,
                    "action_record_status": record.status if record else "unavailable",
                    "proposed_action_type": record.proposed_action.action_type if record else "",
                    "executed_action_type": record.executed_action.action_type if record else "",
                    "intervention_type": record.intervention.intervention_type if record else "",
                    "intervened": record.intervention.intervened if record else "",
                    "blocked": record.intervention.blocked if record else "",
                    "monitor_evaluated": counterfactual.get("monitor_evaluated", ""),
                    "monitor_predicted_unsafe": counterfactual.get("monitor_predicted_unsafe", ""),
                    "proposed_action_score_status": proposed_score.get("status", ""),
                    "proposed_action_unsafe": proposed_score.get("unsafe", ""),
                    "executed_action_unsafe": executed_score.get("unsafe", ""),
                    "realized_unsafe": realized_score.get("unsafe", ""),
                    "intervention_effect": counterfactual.get("intervention_effect", ""),
                    "proposed_action_risk_label": counterfactual.get("proposed_action_risk_label", ""),
                    "allow_action": m.allow_action,
                    "risk_score": m.risk_score,
                    "score_semantics": m.metadata.get("score_semantics", "ordinal_risk_score"),
                    "score_calibration_contract": m.metadata.get("score_calibration_contract", ""),
                    "reasons": ";".join(m.reasons),
                    "metadata_json": canonical_dumps(m.metadata),
                }
            )
    store.write_csv("results/monitor_events.csv", monitor_rows)
    result_config = {
        "artifact_schema_version": "run-results-v2",
        "seed": seed,
        "run_id": run_id,
        "config_digest": config_digest,
        "episode_record_version": EPISODE_RECORD_VERSION,
        "action_record_contract": ACTION_RECORD_CONTRACT,
        "counterfactual_evaluation_contract": COUNTERFACTUAL_EVALUATION_CONTRACT,
        "metric_schema_version": METRIC_SCHEMA_VERSION,
        "monitor_evaluation_schema_version": MONITOR_EVALUATION_SCHEMA_VERSION,
        "scenario_manifest_contract": SCENARIO_MANIFEST_CONTRACT,
        "scenario_family_contract": SCENARIO_FAMILY_CONTRACT,
        "scenario_split_contract": SCENARIO_SPLIT_CONTRACT,
        "scenario_coverage_contract": SCENARIO_COVERAGE_CONTRACT,
        "scenario_coverage_hash": coverage["coverage_hash"],
        "identity": identity,
        "config": config,
        "normalized_config": config,
        "operational_request": operational_request or {},
        "episodes": len(episodes) + len(errors),
        "planned_episodes": len(episodes) + len(errors),
        "completed_episodes": len(episodes),
        "failed_episodes": len(errors),
        "unique_scenarios": len(
            {
                (episode.metadata.get("scenario_manifest") or {}).get("content_hash", episode.scenario_id)
                for episode in episodes
            }
        ),
        "unique_scenario_pairs": len({episode.scenario_pair_id for episode in episodes if episode.scenario_pair_id}),
        "competence_gate": {
            "schema_version": competence.get("schema_version"),
            "passed": competence.get("passed", False),
            "failed_gates": competence.get("failed_gates", []),
        },
        "orchestration_errors": errors,
    }
    store.write_json(
        "results/config.json",
        result_config,
    )
    store.write_json("config/normalized_config.json", config)
    store.write_json("identity/experiment_identity.json", identity or {})
    store.write_json(
        "plugins/descriptors.json",
        {
            "schema_version": "plugin-descriptors-v2",
            "descriptors": plugin_catalog or [],
        },
    )
    store.write_json(
        "status.json",
        {
            "schema_version": "run-status-v1",
            "planned_episodes": result_config["planned_episodes"],
            "started_episodes": len(episodes) + len(errors),
            "completed_episodes": len(episodes),
            "failed_episodes": len(errors),
            "skipped_episodes": 0,
            "pending_episodes": 0,
            "invalid_episodes": 0,
        },
    )
    for episode in episodes:
        store.write_trace(
            episode.episode_id,
            policy={"episode_id": episode.episode_id, "step_trace": episode.metadata.get("step_trace", [])},
            evaluator={
                "episode_id": episode.episode_id,
                "trace": episode.metadata.get("evaluator_trace", []),
                "action_records": [record.to_dict() for record in episode.action_records],
            },
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Tool-Agent Shift Benchmark")
    parser.add_argument("--config", default="small")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--env", choices=list(ENVS))
    parser.add_argument("--agent", choices=list(AGENTS))
    parser.add_argument("--all-envs", action="store_true")
    parser.add_argument("--all-agents", action="store_true")
    args = parser.parse_args(argv)
    store = ArtifactStore(prepare_run_dir())
    episodes = run_eval(
        args.config,
        args.seed,
        env=args.env,
        agent=args.agent,
        all_envs=args.all_envs,
        all_agents=args.all_agents,
        artifact_store=store,
        checkpoint_path=str(store.run_dir / "checkpoint.json"),
    )
    store.finalize(command=["python", "-m", "tool_agent_shift_benchmark.run_eval"])
    print(f"wrote results for {len(episodes)} episodes")


if __name__ == "__main__":
    main()
