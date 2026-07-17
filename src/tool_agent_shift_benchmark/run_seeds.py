from __future__ import annotations

import argparse
import csv

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.config import load_config
from tool_agent_shift_benchmark.core.run_artifacts import prepare_run_dir
from tool_agent_shift_benchmark.core.serialization import stable_hash
from tool_agent_shift_benchmark.metrics.confidence import confidence_intervals, paired_effect_intervals
from tool_agent_shift_benchmark.metrics.outcomes import METRIC_SCHEMA_VERSION
from tool_agent_shift_benchmark.metrics.statistics import AnalysisConfig, plan_paired_sample_size
from tool_agent_shift_benchmark.run_eval import run_eval


def _read_rows(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_analysis_bundle_scaffold(
    artifact_store: ArtifactStore,
    *,
    config: dict[str, object],
    seeds: list[int],
    seed_run_ids: list[str],
    source_episode_count: int,
    all_envs: bool,
    all_agents: bool,
) -> None:
    """Describe the parent as an analysis bundle over finalized child runs."""

    normalized_config = {
        **config,
        "analysis_kind": "multi_seed_scenario_clustered",
        "all_environments": all_envs,
        "all_agents": all_agents,
        "seeds": seeds,
        "source_run_ids": seed_run_ids,
    }
    semantic = {
        "analysis_kind": normalized_config["analysis_kind"],
        "all_environments": all_envs,
        "all_agents": all_agents,
        "normalized_config": config,
        "seeds": seeds,
        "source_run_ids": seed_run_ids,
    }
    identity = {
        "schema_version": "multi-seed-analysis-v1",
        "run_id": stable_hash(semantic, prefix="run"),
        "config_digest": stable_hash(normalized_config, prefix="cfg"),
        "semantic": semantic,
        "operational": {"source_bundle_count": len(seed_run_ids)},
    }
    plan = {
        "schema_version": "execution-plan-v1",
        "run_id": identity["run_id"],
        "config_digest": identity["config_digest"],
        "identity": identity,
        "normalized_config": normalized_config,
        "request": {"analysis_kind": normalized_config["analysis_kind"]},
        "execution_mode": "multi_seed_analysis",
        "dimensions": {"seeds": seeds, "source_run_ids": seed_run_ids},
        # Scientific episode records remain in finalized child bundles. The
        # parent plans no direct episodes and cannot masquerade as an executor.
        "episodes": [],
    }
    artifact_store.write_json("config/normalized_config.json", normalized_config)
    artifact_store.write_json("identity/experiment_identity.json", identity)
    artifact_store.write_json(
        "plugins/descriptors.json",
        {"schema_version": "plugin-descriptors-v2", "descriptors": []},
    )
    artifact_store.write_json("plan/execution_plan.json", plan)
    artifact_store.write_jsonl("results/episodes.jsonl", ())
    artifact_store.write_jsonl("results/orchestration_errors.jsonl", ({"orchestration_errors": []},))
    artifact_store.write_json(
        "status.json",
        {
            "schema_version": "run-status-v1",
            "planned_episodes": 0,
            "started_episodes": 0,
            "completed_episodes": 0,
            "failed_episodes": 0,
            "skipped_episodes": 0,
            "pending_episodes": 0,
            "invalid_episodes": 0,
            "source_completed_episodes": source_episode_count,
        },
    )
    artifact_store.write_json(
        "results/config.json",
        {
            "artifact_schema_version": "run-results-v2",
            "run_id": identity["run_id"],
            "config_digest": identity["config_digest"],
            "identity": identity,
            "config": normalized_config,
            "normalized_config": normalized_config,
            "metric_schema_version": METRIC_SCHEMA_VERSION,
            "analysis_schema_version": AnalysisConfig().schema_version,
            "planned_episodes": 0,
            "completed_episodes": 0,
            "failed_episodes": 0,
            "source_completed_episodes": source_episode_count,
            "source_run_ids": seed_run_ids,
        },
    )


def run_seeds(
    config_path: str,
    all_envs: bool = False,
    all_agents: bool = False,
    *,
    artifact_store: ArtifactStore,
):
    cfg = load_config(config_path)
    seeds = [int(s) for s in (cfg.get("seeds") or [42, 43, 44])]
    seed_rows = []
    unit_rows = []
    seed_run_ids = []
    for seed in seeds:
        seed_store = ArtifactStore(artifact_store.run_dir / "seed_runs" / f"seed-{seed}")
        run_eval(
            config_path,
            seed=seed,
            all_envs=all_envs,
            all_agents=all_agents,
            artifact_store=seed_store,
        )
        seed_manifest = seed_store.finalize(command=["tasb", "run-seeds", "--seed", str(seed)])
        seed_run_ids.append(str(seed_manifest["run_id"]))
        for row in _read_rows(str(seed_store.run_dir / "results" / "summary.csv")):
            row = dict(row)
            row["seed"] = seed
            seed_rows.append(row)
        unit_rows.extend(_read_rows(str(seed_store.run_dir / "results" / "episode_outcomes.csv")))
    _write_analysis_bundle_scaffold(
        artifact_store,
        config=cfg,
        seeds=seeds,
        seed_run_ids=seed_run_ids,
        source_episode_count=len(unit_rows),
        all_envs=all_envs,
        all_agents=all_agents,
    )
    artifact_store.write_csv("results/seed_summary.csv", seed_rows)
    analysis_config = AnalysisConfig()
    ci_rows = confidence_intervals(unit_rows, config=analysis_config)
    paired_rows = paired_effect_intervals(unit_rows, config=analysis_config)
    artifact_store.write_csv("results/confidence_intervals.csv", ci_rows)
    artifact_store.write_csv("results/paired_effect_intervals.csv", paired_rows)
    artifact_store.write_json("analysis/statistical_analysis_config.json", analysis_config.to_dict())
    artifact_store.write_json(
        "analysis/sample_size_plan.json",
        {
            "analysis_schema_version": analysis_config.schema_version,
            "assumption": "paired scenario-level effects with standard deviation 0.5",
            "plans": [plan_paired_sample_size(effect, 0.5).to_dict() for effect in (0.05, 0.1, 0.2)],
        },
    )
    return seed_rows, ci_rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run multi-seed Tool-Agent Shift Benchmark")
    parser.add_argument("--config", default="seeds")
    parser.add_argument("--all-envs", action="store_true")
    parser.add_argument("--all-agents", action="store_true")
    parser.add_argument("--run-name")
    args = parser.parse_args(argv)
    store = ArtifactStore(prepare_run_dir(args.run_name))
    seed_rows, ci_rows = run_seeds(
        args.config,
        all_envs=args.all_envs,
        all_agents=args.all_agents,
        artifact_store=store,
    )
    store.finalize(command=["python", "-m", "tool_agent_shift_benchmark.run_seeds"])
    print(
        f"multi-seed episodes: {sum(int(float(r.get('episodes', 0))) for r in seed_rows)}; "
        f"seed rows: {len(seed_rows)}; ci rows: {len(ci_rows)}"
    )


if __name__ == "__main__":
    main()
