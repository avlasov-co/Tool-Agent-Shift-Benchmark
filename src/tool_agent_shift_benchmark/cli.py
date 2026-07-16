from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from tool_agent_shift_benchmark.analysis.run_analysis import run_analysis
from tool_agent_shift_benchmark.analysis.run_pairwise_compounds import write_pairwise_compound_matrix
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.config import dump_config_yaml, load_config, load_raw_config, write_config_yaml
from tool_agent_shift_benchmark.core.config_schema import migrate_config_data, validate_config
from tool_agent_shift_benchmark.core.contracts import CONTRACT_VERSION
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.execution import ExecutionRequest, normalize_execution_request
from tool_agent_shift_benchmark.core.monitoring import MONITOR_MODE_ORDER
from tool_agent_shift_benchmark.core.oversight import OVERSIGHT_MODE_ORDER
from tool_agent_shift_benchmark.core.run_artifacts import (
    prepare_run_dir,
    resolve_run,
    restore_run_to_workspace,
    run_results_dir,
    snapshot_outputs,
)
from tool_agent_shift_benchmark.core.serialization import canonical_dumps, canonical_loads
from tool_agent_shift_benchmark.generate_report import main as generate_report_main
from tool_agent_shift_benchmark.package_resources import builtin_config_names
from tool_agent_shift_benchmark.plot_results import main as plot_results_main
from tool_agent_shift_benchmark.reporting.failure_cases import format_replay, replay_case
from tool_agent_shift_benchmark.reporting.html_report import render_html_report
from tool_agent_shift_benchmark.run_eval import run_eval


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
                Episode.from_dict(canonical_loads(line))
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
        monitor_modes=args.monitor_mode,
        oversight_modes=args.oversight_mode,
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
                "seed": args.seed if args.seed is not None else load_config(args.config)["seed"],
                "episodes": len(episodes),
                "workers": args.workers if args.workers is not None else load_config(args.config)["workers"],
                "plugin_catalog": catalog.as_dict(),
                "contract_version": CONTRACT_VERSION,
            },
        )
        print(f"run artifacts written to {run_dir}")
    print(f"wrote results for {len(episodes)} episodes")


def _plugins_command(args: argparse.Namespace) -> None:
    catalog = PluginCatalog()
    if args.plugins_command == "list":
        for descriptor in catalog.descriptors():
            print(f"{descriptor.kind}\t{descriptor.name}\t{descriptor.version}\tcontract={descriptor.contract_version}")
        for error in catalog.discovery_errors():
            print(f"{error['kind']}\t{error['name']}\tERROR\t{error['error']}")
    else:
        catalog.validate()
        print(f"plugin catalog valid: {len(catalog.descriptors())} plugins")


def _plan_command(args: argparse.Namespace) -> None:
    request = ExecutionRequest(
        config_path=args.config,
        mode="replay" if args.replay_episode_id else "ordinary",
        seed=args.seed,
        scenario_indices=tuple(args.scenario_index or ()),
        episode_ids=tuple(args.episode_id or ()),
        selection_offset=args.offset,
        selection_limit=args.limit,
        partition_index=args.partition_index,
        partition_count=args.partition_count,
        replay_episode_ids=tuple(args.replay_episode_id or ()),
        monitor_modes=tuple(args.monitor_mode or ()),
        oversight_modes=tuple(args.oversight_mode or ()),
    )
    execution_plan = normalize_execution_request(request)
    print(
        canonical_dumps(
            {
                "run_id": execution_plan.planner.run_id,
                "config_digest": execution_plan.planner.config_digest,
                "identity": execution_plan.planner.identity.to_dict(),
                "plugins": execution_plan.planner.catalog.as_dict(),
                "execution": execution_plan.to_dict(),
                "episodes": len(execution_plan.episodes),
                "matrix": [item.to_dict() for item in execution_plan.episodes],
                "seed_policy": "stable hash(run, environment, agent, shift, severity, scenario_index)",
                "workers": execution_plan.spec.workers,
                "artifact_paths": [
                    f"runs/{args.run_name or execution_plan.planner.run_id}/run_manifest.json",
                    "results/episodes.jsonl",
                    "traces/policy/",
                    "traces/evaluator/",
                ],
            },
            pretty=True,
        )
    )


def _inspect_run_command(args: argparse.Namespace) -> None:
    run_dir = resolve_run(args.run)
    if run_dir is None:
        raise FileNotFoundError("no run found")
    manifest = run_dir / "run_manifest.json"
    print(manifest.read_text(encoding="utf-8") if manifest.exists() else canonical_dumps({"run_dir": str(run_dir)}))


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
    print(canonical_dumps(manifest["outputs"], pretty=True))


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
    print(canonical_dumps(manifest, pretty=True))


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
    validate_config(args.path, pairwise=args.pairwise)
    print(f"config valid (schema v2): {args.path}")


def _migrate_config_command(args: argparse.Namespace) -> None:
    model, decisions = migrate_config_data(load_raw_config(args.path), source=args.path)
    for decision in decisions:
        print(f"migration decision: {decision}", file=sys.stderr)
    if args.output:
        output = write_config_yaml(args.output, model.to_dict())
        print(f"migrated config written to {output}")
    else:
        print(dump_config_yaml(model.to_dict()), end="")


def _list_builtin_configs_command(args: argparse.Namespace) -> None:
    for name in builtin_config_names():
        print(name)


def _verify_release_command(args: argparse.Namespace) -> None:
    subprocess.run([sys.executable, "-m", "tool_agent_shift_benchmark.release_verification"], check=True)


def _clean_command(args: argparse.Namespace) -> None:
    subprocess.run(["bash", "scripts/clean_outputs.sh"], check=True)
    if args.runs and Path("runs").exists():
        shutil.rmtree("runs")
    print("clean complete")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tasb", description="Tool-Agent Shift Benchmark CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run benchmark evaluation")
    run.add_argument("--config", default="small")
    run.add_argument("--seed", type=int)
    run.add_argument("--env")
    run.add_argument("--agent")
    run.add_argument("--all-envs", action="store_true")
    run.add_argument("--all-agents", action="store_true")
    run.add_argument("--run-name")
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--workers", type=int)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--scenario-index", type=int, action="append")
    run.add_argument("--episode-id", action="append")
    run.add_argument("--offset", type=int)
    run.add_argument("--limit", type=int)
    run.add_argument("--partition-index", type=int)
    run.add_argument("--partition-count", type=int)
    run.add_argument("--replay-episode-id", action="append")
    run.add_argument("--monitor-mode", action="append", choices=MONITOR_MODE_ORDER)
    run.add_argument("--oversight-mode", action="append", choices=OVERSIGHT_MODE_ORDER)
    run.set_defaults(func=_run_command)

    analyze = sub.add_parser("analyze", help="generate post-hoc analysis")
    analyze.add_argument("--run")
    analyze.add_argument("--analysis-dir")
    analyze.set_defaults(func=_analyze_command)

    pairwise = sub.add_parser("pairwise", help="run pairwise compound analysis")
    pairwise.add_argument("--config", default="compound_matrix")
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

    config = sub.add_parser("config", help="validate or migrate versioned configuration")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_validate = config_sub.add_parser("validate", help="validate a schema-v2 config")
    config_validate.add_argument("path")
    config_validate.add_argument("--pairwise", action="store_true")
    config_validate.set_defaults(func=_validate_config_command)
    config_migrate = config_sub.add_parser("migrate", help="migrate a legacy v1 config deterministically")
    config_migrate.add_argument("path")
    config_migrate.add_argument("--output")
    config_migrate.set_defaults(func=_migrate_config_command)
    config_list = config_sub.add_parser("list", help="list packaged built-in configurations")
    config_list.set_defaults(func=_list_builtin_configs_command)

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
    plan.add_argument("--config", default="small")
    plan.add_argument("--seed", type=int)
    plan.add_argument("--run-name")
    plan.add_argument("--scenario-index", type=int, action="append")
    plan.add_argument("--episode-id", action="append")
    plan.add_argument("--offset", type=int)
    plan.add_argument("--limit", type=int)
    plan.add_argument("--partition-index", type=int)
    plan.add_argument("--partition-count", type=int)
    plan.add_argument("--replay-episode-id", action="append")
    plan.add_argument("--monitor-mode", action="append", choices=MONITOR_MODE_ORDER)
    plan.add_argument("--oversight-mode", action="append", choices=OVERSIGHT_MODE_ORDER)
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
