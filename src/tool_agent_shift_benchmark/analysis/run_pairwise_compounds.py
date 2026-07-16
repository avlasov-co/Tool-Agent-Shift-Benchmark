from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tool_agent_shift_benchmark.agents import AGENTS
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.config import load_config
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.execution import (
    ExecutionRequest,
    execute_plan,
    plan_execution_config,
)
from tool_agent_shift_benchmark.core.orchestration import EpisodeSpec
from tool_agent_shift_benchmark.core.serialization import write_csv, write_json
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment
from tool_agent_shift_benchmark.faults import FAULTS
from tool_agent_shift_benchmark.metrics.aggregation import aggregate_group

ENVS = {
    "file_ops": FileOpsEnvironment,
    "calendar_ops": CalendarOpsEnvironment,
    "risk_ops": RiskOpsEnvironment,
}
ANALYSIS_DIR = Path("results/analysis")
DEFAULT_CONFIG = "compound_matrix"


@dataclass(frozen=True)
class PairwiseEpisodeSpec:
    episode: EpisodeSpec
    fault_names: tuple[str, ...]

    @property
    def run_id(self) -> str:
        return self.episode.run_id

    @property
    def scenario_id(self) -> str:
        return self.episode.scenario_id

    @property
    def scenario_pair_id(self) -> str:
        return self.episode.scenario_pair_id

    @property
    def episode_id(self) -> str:
        return self.episode.episode_id

    @property
    def scenario_seed(self) -> int:
        return self.episode.seed


def _pairwise_execution_plan(
    *,
    env_name: str,
    agent_name: str,
    fault_names: tuple[str, ...],
    severity: float,
    episodes_per_combo: int,
    seed: int,
):
    """Build pairwise treatments through the ordinary normalized planner."""

    selected_chain = list(fault_names or ("normal",))
    config = {
        "schema_version": 2,
        "environments": [env_name],
        "agents": [agent_name],
        "faults": selected_chain,
        "shift_chains": [selected_chain],
        "fault_severities": [severity],
        "episodes_per_combo": episodes_per_combo,
        "episode_steps": 6,
        "monitor_modes": ["full_composite_monitor"],
        "oversight_modes": ["record_only"],
    }
    request = ExecutionRequest(
        config_path="<pairwise_compound>",
        mode="pairwise_compound",
        seed=seed,
        environments=(env_name,),
        agents=(agent_name,),
    )
    return plan_execution_config(request, config, catalog=PluginCatalog(include_external=False))


def parse_pair(pair: str) -> tuple[str, str]:
    parts = [p.strip() for p in pair.replace(",", "+").split("+") if p.strip()]
    if len(parts) != 2:
        raise ValueError(f"fault pair must contain exactly two faults: {pair!r}")
    for name in parts:
        if name not in FAULTS or name in {"normal", "compound_shift"}:
            raise ValueError(f"unsupported pairwise fault {name!r}")
    if parts[0] == parts[1]:
        raise ValueError(f"fault pair must contain two different faults: {pair!r}")
    return parts[0], parts[1]


def _plan_fault_combo(
    *,
    env_name: str,
    agent_name: str,
    fault_names: tuple[str, ...],
    severity: float,
    episodes_per_combo: int,
    seed: int,
) -> list[PairwiseEpisodeSpec]:
    plan = _pairwise_execution_plan(
        env_name=env_name,
        agent_name=agent_name,
        fault_names=fault_names,
        severity=severity,
        episodes_per_combo=episodes_per_combo,
        seed=seed,
    )
    target = "+".join(fault_names) if fault_names else "normal"
    return [PairwiseEpisodeSpec(item, fault_names) for item in plan.episodes if item.shift == target]


def _run_fault_combo(
    *,
    env_name: str,
    agent_name: str,
    fault_names: tuple[str, ...],
    severity: float,
    episodes_per_combo: int,
    seed: int,
) -> list[Episode]:
    plan = _pairwise_execution_plan(
        env_name=env_name,
        agent_name=agent_name,
        fault_names=fault_names,
        severity=severity,
        episodes_per_combo=episodes_per_combo,
        seed=seed,
    )
    result = execute_plan(plan, catalog=plan.planner.catalog, run_competence_preflight=False)
    target = "+".join(fault_names) if fault_names else "normal"
    return [episode for episode in result.episodes if episode.fault.name == target]


def _metrics(episodes: list[Episode]) -> dict[str, float]:
    return aggregate_group(episodes)


def _delta(pair_metrics: dict[str, float], baseline: dict[str, float], metric: str) -> float:
    return round(float(pair_metrics.get(metric, 0.0)) - float(baseline.get(metric, 0.0)), 6)


def build_pairwise_compound_matrix(
    config_path: str = DEFAULT_CONFIG,
) -> list[dict[str, Any]]:
    cfg = load_config(config_path)
    env_names = list(cfg.get("environments", list(ENVS)))
    agent_names = list(cfg.get("agents", list(AGENTS)))
    severities = [float(s) for s in cfg.get("fault_severities", [1.0])]
    pairs = [parse_pair(str(pair)) for pair in cfg.get("fault_pairs", [])]
    episodes_per_combo = int(cfg.get("episodes_per_combo", 2))
    seed = int(cfg.get("seed", 42))

    rows: list[dict[str, Any]] = []
    metric_names = [
        "unsafe_action_rate",
        "coverage",
        "safe_useful_action_rate",
        "recovery_rate",
        "monitor_recall",
        "monitor_false_positive_rate",
    ]
    cache: dict[tuple[str, str, tuple[str, ...], float], dict[str, float]] = {}

    def metrics_for(env_name: str, agent_name: str, faults: tuple[str, ...], severity: float) -> dict[str, float]:
        key = (env_name, agent_name, faults, severity)
        if key not in cache:
            cache[key] = _metrics(
                _run_fault_combo(
                    env_name=env_name,
                    agent_name=agent_name,
                    fault_names=faults,
                    severity=severity,
                    episodes_per_combo=episodes_per_combo,
                    seed=seed,
                )
            )
        return cache[key]

    for env_name in env_names:
        if env_name not in ENVS:
            raise ValueError(f"unknown environment {env_name!r}")
        for agent_name in agent_names:
            if agent_name not in AGENTS:
                raise ValueError(f"unknown agent {agent_name!r}")
            for severity in severities:
                clean = metrics_for(env_name, agent_name, tuple(), severity)
                for fault_a, fault_b in pairs:
                    a_metrics = metrics_for(env_name, agent_name, (fault_a,), severity)
                    b_metrics = metrics_for(env_name, agent_name, (fault_b,), severity)
                    pair_metrics = metrics_for(env_name, agent_name, (fault_a, fault_b), severity)
                    worst_single = (
                        a_metrics
                        if a_metrics.get("unsafe_action_rate", 0.0) >= b_metrics.get("unsafe_action_rate", 0.0)
                        else b_metrics
                    )
                    worst_single_name = fault_a if worst_single is a_metrics else fault_b
                    row: dict[str, Any] = {
                        "environment": env_name,
                        "agent": agent_name,
                        "fault_a": fault_a,
                        "fault_b": fault_b,
                        "fault_pair": f"{fault_a}+{fault_b}",
                        "fault_severity": severity,
                        "episodes_per_combo": episodes_per_combo,
                        "seed": seed,
                        "worst_single_fault": worst_single_name,
                    }
                    for metric in metric_names:
                        row[f"clean_{metric}"] = round(float(clean.get(metric, 0.0)), 6)
                        row[f"fault_a_{metric}"] = round(float(a_metrics.get(metric, 0.0)), 6)
                        row[f"fault_b_{metric}"] = round(float(b_metrics.get(metric, 0.0)), 6)
                        row[f"pair_{metric}"] = round(float(pair_metrics.get(metric, 0.0)), 6)
                        row[f"delta_pair_vs_clean_{metric}"] = _delta(pair_metrics, clean, metric)
                        row[f"delta_pair_vs_worst_single_{metric}"] = _delta(pair_metrics, worst_single, metric)
                    rows.append(row)
    return rows


def write_pairwise_compound_matrix(
    config_path: str = DEFAULT_CONFIG, output_dir: str | Path = ANALYSIS_DIR
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = build_pairwise_compound_matrix(config_path)
    csv_path = out / "pairwise_compound_matrix.csv"
    write_csv(csv_path, rows)
    summary = {
        "config_path": config_path,
        "rows": len(rows),
        "output_csv": str(csv_path),
        "description": "Pairwise compound-fault matrix comparing clean, single-fault, and paired-fault behavior.",
    }
    write_json(out / "pairwise_compound_manifest.json", summary)
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run pairwise compound-shift analysis")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", default=str(ANALYSIS_DIR))
    args = parser.parse_args(argv)
    manifest = write_pairwise_compound_matrix(args.config, args.output_dir)
    print(f"pairwise compound matrix complete: rows={manifest['rows']} output={manifest['output_csv']}")


if __name__ == "__main__":
    main()
