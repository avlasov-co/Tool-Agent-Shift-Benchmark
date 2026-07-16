from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any

from tool_agent_shift_benchmark.agents import AGENTS
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.config import load_config
from tool_agent_shift_benchmark.core.context import ObservationContext, redact_response_for_policy
from tool_agent_shift_benchmark.core.contracts import IdentityMismatchError
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.identity import (
    EVALUATOR_NAME,
    EVALUATOR_VERSION,
    IDENTITY_SCHEMA_VERSION,
    ComponentIdentity,
    PlannedEpisodeIdentity,
)
from tool_agent_shift_benchmark.core.serialization import write_csv, write_json
from tool_agent_shift_benchmark.core.types import FaultConfig, MonitorDecision, stable_hash
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment
from tool_agent_shift_benchmark.faults import FAULTS
from tool_agent_shift_benchmark.metrics.aggregation import aggregate_group
from tool_agent_shift_benchmark.monitors.composite import CompositeMonitor

ENVS = {
    "file_ops": FileOpsEnvironment,
    "calendar_ops": CalendarOpsEnvironment,
    "risk_ops": RiskOpsEnvironment,
}
ANALYSIS_DIR = Path("results/analysis")
DEFAULT_CONFIG = "configs/compound_matrix.yaml"


@dataclass(frozen=True)
class PairwiseEpisodeSpec:
    identity: PlannedEpisodeIdentity
    scenario_index: int
    environment: str
    agent: str
    fault_names: tuple[str, ...]
    severity: float

    @property
    def run_id(self) -> str:
        return self.identity.run_id

    @property
    def scenario_id(self) -> str:
        return self.identity.scenario_id

    @property
    def scenario_pair_id(self) -> str:
        if self.identity.scenario_pair_id is None:
            raise RuntimeError("pairwise episode is missing scenario_pair_id")
        return self.identity.scenario_pair_id

    @property
    def episode_id(self) -> str:
        return self.identity.episode_id

    @property
    def scenario_seed(self) -> int:
        return self.identity.scenario_seed


def _component(catalog: PluginCatalog, kind: str, name: str) -> ComponentIdentity:
    descriptor = catalog.descriptor(kind, name)
    return ComponentIdentity(kind, descriptor.name, descriptor.version, descriptor.contract_version)


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


def _monitor_decision(
    agent_name: str,
    agent_obj: object,
    context: ObservationContext,
    observation: object,
    action: object,
) -> MonitorDecision:
    if agent_name == "monitor_gated" and getattr(agent_obj, "last_monitor_decision", None) is not None:
        return agent_obj.last_monitor_decision
    return CompositeMonitor().check(context, observation, action)


def _plan_fault_combo(
    *,
    env_name: str,
    agent_name: str,
    fault_names: tuple[str, ...],
    severity: float,
    episodes_per_combo: int,
    seed: int,
) -> list[PairwiseEpisodeSpec]:
    combo_name = "+".join(fault_names) if fault_names else "normal"
    catalog = PluginCatalog(include_external=False)
    environment = _component(catalog, "environment", env_name)
    agent = _component(catalog, "agent", agent_name)
    shift_chain = tuple(_component(catalog, "shift", name) for name in (fault_names or ("normal",)))
    monitor = _component(catalog, "monitor", "composite")
    evaluator = ComponentIdentity("evaluator", EVALUATOR_NAME, EVALUATOR_VERSION, "1")
    run_id = stable_hash(
        {
            "identity_schema_version": IDENTITY_SCHEMA_VERSION,
            "kind": "pairwise_compound_matrix",
            "environment": environment,
            "agent": agent,
            "faults": shift_chain,
            "severity": severity,
            "episodes_per_combo": episodes_per_combo,
            "seed": seed,
            "monitor": monitor,
            "evaluator": evaluator,
        },
        prefix="pairrun",
    )
    planned: list[PairwiseEpisodeSpec] = []
    for index in range(episodes_per_combo):
        scenario_id = f"{env_name}_scenario_{index}"
        scenario_pair_id = stable_hash(
            {
                "kind": "pairwise_scenario",
                "identity_schema_version": IDENTITY_SCHEMA_VERSION,
                "env": env_name,
                "agent": agent_name,
                "severity": severity,
                "episodes_per_combo": episodes_per_combo,
                "seed": seed,
                "scenario_index": index,
            },
            prefix="pair",
        )
        scenario_seed = int(stable_hash({"pair": scenario_pair_id}, prefix="seed").split("_")[1], 16) % (2**31)
        episode_id = stable_hash(
            {
                "env": env_name,
                "scenario": scenario_id,
                "agent": agent_name,
                "fault": combo_name,
                "severity": severity,
                "seed": scenario_seed,
                "run_id": run_id,
            },
            prefix="ep",
        )
        planned.append(
            PairwiseEpisodeSpec(
                PlannedEpisodeIdentity(
                    IDENTITY_SCHEMA_VERSION,
                    run_id,
                    scenario_id,
                    scenario_seed,
                    scenario_pair_id,
                    episode_id,
                    environment,
                    agent,
                    shift_chain,
                    monitor,
                    evaluator,
                ),
                index,
                env_name,
                agent_name,
                fault_names,
                severity,
            )
        )
    return planned


def _run_fault_combo(
    *,
    env_name: str,
    agent_name: str,
    fault_names: tuple[str, ...],
    severity: float,
    episodes_per_combo: int,
    seed: int,
) -> list[Episode]:
    episodes: list[Episode] = []
    combo_name = "+".join(fault_names) if fault_names else "normal"
    for item in _plan_fault_combo(
        env_name=env_name,
        agent_name=agent_name,
        fault_names=fault_names,
        severity=severity,
        episodes_per_combo=episodes_per_combo,
        seed=seed,
    ):
        fault_seed = int(stable_hash({"episode": item.episode_id, "phase": "faults"}, prefix="seed").split("_")[1], 16)
        rng = Random(fault_seed)
        env_obj = ENVS[env_name](seed=item.scenario_seed, scenario_index=item.scenario_index)
        if env_obj.scenario_id != item.scenario_id:
            raise IdentityMismatchError(
                field="environment.scenario_id",
                expected=item.scenario_id,
                actual=env_obj.scenario_id,
                phase="pairwise_environment_identity",
                plugin_descriptor={
                    "kind": item.identity.environment.kind,
                    "name": item.identity.environment.name,
                    "version": item.identity.environment.version,
                    "contract_version": item.identity.environment.contract_version,
                },
                episode_id=item.episode_id,
            )
        agent_obj = AGENTS[agent_name]()
        response = env_obj.tool_response()
        for fault_name in fault_names:
            response = FAULTS[fault_name](severity=severity).apply(response, env_obj, rng)
        policy_response = redact_response_for_policy(response)
        context = ObservationContext.from_environment(env_obj, policy_response.observation)
        decision = agent_obj.decide(context, policy_response)
        monitor = _monitor_decision(agent_name, agent_obj, context, policy_response.observation, decision.action)
        execution = env_obj.execute(decision.action, observed_timestamp=policy_response.observation.timestamp)
        recovered = bool(fault_names and not execution.unsafe and (decision.action.abstain or not monitor.allow_action))
        episodes.append(
            Episode(
                env_name=env_name,
                scenario_id=item.scenario_id,
                agent_name=agent_name,
                fault=FaultConfig(combo_name, severity, {"parts": list(fault_names)}),
                seed=item.scenario_seed,
                run_id=item.run_id,
                episode_id=item.episode_id,
                tool_response=response,
                decision=decision,
                monitor_decisions=[monitor],
                execution=execution,
                metadata={
                    "config_path": DEFAULT_CONFIG,
                    "combo_seed": item.scenario_seed,
                    "episode_steps": 1,
                    "steps_taken": 1,
                    "multi_step": False,
                    "unsafe_step_count": int(execution.unsafe),
                    "failure_step": "0" if execution.unsafe else "",
                    "stop_reason": "unsafe_action"
                    if execution.unsafe
                    else "abstained"
                    if decision.action.abstain
                    else "success"
                    if execution.success
                    else "incomplete",
                    "recovered": recovered,
                    "pairwise_compound_matrix": True,
                },
                scenario_pair_id=item.scenario_pair_id,
                planned_identity=item.identity.to_dict(),
            )
        )
    return episodes


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
