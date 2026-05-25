from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from src.analysis.run_analysis import run_analysis
from src.analysis.run_pairwise_compounds import write_pairwise_compound_matrix
from src.core.config_schema import validate_config
from src.core.run_artifacts import prepare_run_dir, resolve_run, restore_run_to_workspace, run_results_dir, snapshot_outputs
from src.generate_report import main as generate_report_main
from src.plot_results import main as plot_results_main
from src.reporting.failure_cases import format_replay, replay_case
from src.reporting.html_report import render_html_report
from src.run_eval import run_eval


def _run_command(args: argparse.Namespace) -> None:
    validate_config(args.config)
    episodes = run_eval(args.config, args.seed, env=args.env, agent=args.agent, all_envs=args.all_envs, all_agents=args.all_agents)
    run_dir = None
    if args.run_name:
        run_dir = prepare_run_dir(args.run_name, overwrite=args.overwrite)
        snapshot_outputs(run_dir, command=["tasb", "run"], extra_metadata={"config": args.config, "seed": args.seed, "episodes": len(episodes)})
        print(f"run artifacts written to {run_dir}")
    print(f"wrote results for {len(episodes)} episodes")


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
        snapshot_outputs(run_dir, command=["tasb", "analyze"], extra_metadata={"analysis_outputs": manifest.get("outputs", {})})
    print(json.dumps(manifest["outputs"], indent=2, sort_keys=True))


def _pairwise_command(args: argparse.Namespace) -> None:
    validate_config(args.config, pairwise=True)
    output_dir = Path(args.output_dir) if args.output_dir else run_results_dir(args.run) / "analysis"
    manifest = write_pairwise_compound_matrix(args.config, output_dir)
    run_dir = resolve_run(args.run)
    if run_dir:
        snapshot_outputs(run_dir, command=["tasb", "pairwise"], extra_metadata={"pairwise_rows": manifest.get("rows", 0)})
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
        snapshot_outputs(run_dir, command=["tasb", "report"], extra_metadata={"html": bool(args.html)})
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
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
