from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from src.analysis.run_analysis import run_analysis
from src.analysis.run_pairwise_compounds import write_pairwise_compound_matrix
from src.core.catalog import PluginCatalog
from src.core.config import load_config
from src.core.config_schema import validate_config
from src.core.episode import Episode
from src.core.orchestration import ExperimentPlanner, ExperimentSpec
from src.core.run_artifacts import (
    prepare_run_dir,
    resolve_run,
    restore_run_to_workspace,
    run_results_dir,
    snapshot_outputs,
)
from src.generate_report import main as generate_report_main
from src.plot_results import main as plot_results_main
from src.reporting.failure_cases import format_replay, replay_case
from src.reporting.html_report import render_html_report
from src.run_eval import run_eval


def _run_command(args: argparse.Namespace) -> None:
    validate_config(args.config)
    run_dir = None
    existing = []
    if args.resume:
        if not args.run_name:
            raise ValueError("--resume requires --run-name so the checkpoint bundle can be located")
        run_dir = Path("runs") / args.run_name
        episodes_path = run_dir / "results" / "episodes.jsonl"
        if episodes_path.exists():
            existing = [
                Episode.from_dict(json.loads(line))
                for line in episodes_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
    checkpoint = (
        str((run_dir or Path("runs") / (args.run_name or "run-checkpoint")) / "checkpoint.json")
        if args.resume
        else None
    )
    episodes = run_eval(
        args.config,
        args.seed,
        env=args.env,
        agent=args.agent,
        all_envs=args.all_envs,
        all_agents=args.all_agents,
        workers=args.workers,
        existing_episodes=existing,
        checkpoint_path=checkpoint,
        scenario_indices=args.scenario_index,
        episode_ids=args.episode_id,
        selection_offset=args.offset,
        selection_limit=args.limit,
        partition_index=args.partition_index,
        partition_count=args.partition_count,
        replay_episode_ids=args.replay_episode_id,
    )
    if args.run_name:
        if not (args.resume and run_dir and run_dir.exists()):
            run_dir = prepare_run_dir(args.run_name, overwrite=args.overwrite)
        catalog = PluginCatalog()
        snapshot_outputs(
            run_dir,
            command=["tasb", "run"],
            extra_metadata={
                "config": args.config,
                "seed": args.seed,
                "episodes": len(episodes),
                "workers": args.workers,
                "plugin_catalog": catalog.as_dict(),
                "contract_version": "1",
            },
        )
        print(f"run artifacts written to {run_dir}")
    print(f"wrote results for {len(episodes)} episodes")


def _plugins_command(args: argparse.Namespace) -> None:
    catalog = PluginCatalog()
    if args.plugins_command == "list":
        for descriptor in catalog.descriptors():
            print(f"{descriptor.kind}\t{descriptor.name}\t{descriptor.version}\tcontract={descriptor.contract_version}")
    else:
        catalog.validate()
        print(f"plugin catalog valid: {len(catalog.descriptors())} plugins")


def _plan_command(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    spec = ExperimentSpec.from_config(
        config,
        seed=args.seed,
        scenario_indices=args.scenario_index,
        episode_ids=args.episode_id,
        selection_offset=args.offset,
        selection_limit=args.limit,
        partition_index=args.partition_index,
        partition_count=args.partition_count,
        replay_episode_ids=args.replay_episode_id,
    )
    planner = ExperimentPlanner(spec)
    plan = planner.plan()
    print(
        json.dumps(
            {
                "run_id": planner.run_id,
                "config_digest": planner.config_digest,
                "identity": planner.identity.to_dict(),
                "plugins": planner.catalog.as_dict(),
                "episodes": len(plan),
                "matrix": [item.to_dict() for item in plan],
                "seed_policy": "stable hash(run, environment, agent, shift, severity, scenario_index)",
                "workers": spec.workers,
                "artifact_paths": [
                    f"runs/{args.run_name or planner.run_id}/run_manifest.json",
                    "results/episodes.jsonl",
                    "traces/policy/",
                    "traces/evaluator/",
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


def _inspect_run_command(args: argparse.Namespace) -> None:
    run_dir = resolve_run(args.run)
    if run_dir is None:
        raise FileNotFoundError("no run found")
    manifest = run_dir / "run_manifest.json"
    print(manifest.read_text(encoding="utf-8") if manifest.exists() else json.dumps({"run_dir": str(run_dir)}))


def _render_architecture_command(args: argparse.Namespace) -> None:
    subprocess.run(["bash", "scripts/render_architecture.sh"], check=True)
    print("architecture renders written to docs/architecture.svg and docs/architecture.png")


def _analyze_command(args: argparse.Namespace) -> None:
    results_dir = run_results_dir(args.run)
    analysis_dir = Path(args.analysis_dir) if args.analysis_dir else results_dir / "analysis"
    manifest = run_analysis(results_dir, analysis_dir)
    run_dir = resolve_run(args.run)
    if run_dir:
        docs_src = Path("docs/analysis_report.md")
        if docs_src.exists():
            (run_dir / "docs").mkdir(parents=True, exist_ok=True)
            shutil.copy2(docs_src, run_dir / "docs" / "analysis_report.md")
        snapshot_outputs(
            run_dir,
            command=["tasb", "analyze"],
            extra_metadata={"analysis_outputs": manifest.get("outputs", {})},
        )
    print(json.dumps(manifest["outputs"], indent=2, sort_keys=True))


def _pairwise_command(args: argparse.Namespace) -> None:
    validate_config(args.config, pairwise=True)
    output_dir = Path(args.output_dir) if args.output_dir else run_results_dir(args.run) / "analysis"
    manifest = write_pairwise_compound_matrix(args.config, output_dir)
    run_dir = resolve_run(args.run)
    if run_dir:
        snapshot_outputs(
            run_dir,
            command=["tasb", "pairwise"],
            extra_metadata={"pairwise_rows": manifest.get("rows", 0)},
        )
    print(json.dumps(manifest, indent=2, sort_keys=True))


def _plot_command(args: argparse.Namespace) -> None:
    if args.run:
        restore_run_to_workspace(args.run)
    plot_results_main()
    run_dir = resolve_run(args.run)
    if run_dir:
        snapshot_outputs(run_dir, command=["tasb", "plot"])


def _report_command(args: argparse.Namespace) -> None:
    if args.run:
        restore_run_to_workspace(args.run)
    generate_report_main()
    if args.html:
        output = Path(args.output) if args.output else Path("docs/analysis_report.html")
        render_html_report("results", output)
    run_dir = resolve_run(args.run)
    if run_dir:
        snapshot_outputs(
            run_dir,
            command=["tasb", "report"],
            extra_metadata={"html": bool(args.html)},
        )
    print("report generation complete")


def _replay_command(args: argparse.Namespace) -> None:
    path = Path(args.path) if args.path else run_results_dir(args.run) / "failure_cases.csv"
    analysis_dir = Path(args.analysis_dir) if args.analysis_dir else run_results_dir(args.run) / "analysis"
    print(format_replay(replay_case(args.case_id, str(path), analysis_dir), args.format))


def _validate_config_command(args: argparse.Namespace) -> None:
    warnings = validate_config(args.path, pairwise=args.pairwise)
    for warning in warnings:
        print(f"warning: {warning}")
    print(f"config valid: {args.path}")


def _verify_release_command(args: argparse.Namespace) -> None:
    subprocess.run(["bash", "scripts/verify_release.sh"], check=True)


def _clean_command(args: argparse.Namespace) -> None:
    subprocess.run(["bash", "scripts/clean_outputs.sh"], check=True)
    if args.runs and Path("runs").exists():
        shutil.rmtree("runs")
    print("clean complete")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tasb", description="Tool-Agent Shift Benchmark CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run benchmark evaluation")
    run.add_argument("--config", default="configs/small.yaml")
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--env")
    run.add_argument("--agent")
    run.add_argument("--all-envs", action="store_true")
    run.add_argument("--all-agents", action="store_true")
    run.add_argument("--run-name")
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--workers", type=int, default=1)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--scenario-index", type=int, action="append")
    run.add_argument("--episode-id", action="append")
    run.add_argument("--offset", type=int, default=0)
    run.add_argument("--limit", type=int)
    run.add_argument("--partition-index", type=int)
    run.add_argument("--partition-count", type=int)
    run.add_argument("--replay-episode-id", action="append")
    run.set_defaults(func=_run_command)

    analyze = sub.add_parser("analyze", help="generate post-hoc analysis")
    analyze.add_argument("--run")
    analyze.add_argument("--analysis-dir")
    analyze.set_defaults(func=_analyze_command)

    pairwise = sub.add_parser("pairwise", help="run pairwise compound analysis")
    pairwise.add_argument("--config", default="configs/compound_matrix.yaml")
    pairwise.add_argument("--run")
    pairwise.add_argument("--output-dir")
    pairwise.set_defaults(func=_pairwise_command)

    plot = sub.add_parser("plot", help="generate plots")
    plot.add_argument("--run")
    plot.set_defaults(func=_plot_command)

    report = sub.add_parser("report", help="generate markdown or HTML report")
    report.add_argument("--run")
    report.add_argument("--html", action="store_true")
    report.add_argument("--output")
    report.set_defaults(func=_report_command)

    replay = sub.add_parser("replay", help="replay failure case")
    replay.add_argument("case_id")
    replay.add_argument("--run")
    replay.add_argument("--path")
    replay.add_argument("--analysis-dir")
    replay.add_argument("--format", choices=["json", "markdown", "text"], default="json")
    replay.set_defaults(func=_replay_command)

    validate = sub.add_parser("validate-config", help="validate config file")
    validate.add_argument("path")
    validate.add_argument("--pairwise", action="store_true")
    validate.set_defaults(func=_validate_config_command)

    verify = sub.add_parser("verify-release", help="run release verifier")
    verify.set_defaults(func=_verify_release_command)

    clean = sub.add_parser("clean", help="clean generated outputs")
    clean.add_argument("--runs", action="store_true")
    clean.set_defaults(func=_clean_command)

    plugins = sub.add_parser("plugins", help="inspect plugin catalog")
    plugins_sub = plugins.add_subparsers(dest="plugins_command", required=True)
    plugins_list = plugins_sub.add_parser("list")
    plugins_list.set_defaults(func=_plugins_command)
    plugins_validate = plugins_sub.add_parser("validate")
    plugins_validate.set_defaults(func=_plugins_command)

    plan = sub.add_parser("plan", help="resolve an experiment without running it")
    plan.add_argument("--config", default="configs/small.yaml")
    plan.add_argument("--seed", type=int, default=42)
    plan.add_argument("--run-name")
    plan.add_argument("--scenario-index", type=int, action="append")
    plan.add_argument("--episode-id", action="append")
    plan.add_argument("--offset", type=int, default=0)
    plan.add_argument("--limit", type=int)
    plan.add_argument("--partition-index", type=int)
    plan.add_argument("--partition-count", type=int)
    plan.add_argument("--replay-episode-id", action="append")
    plan.set_defaults(func=_plan_command)

    inspect = sub.add_parser("inspect-run", help="show a run manifest")
    inspect.add_argument("run")
    inspect.set_defaults(func=_inspect_run_command)

    render = sub.add_parser("render-architecture", help="render the Mermaid architecture diagram")
    render.set_defaults(func=_render_architecture_command)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
