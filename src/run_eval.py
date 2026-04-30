from __future__ import annotations

import argparse
import json
from pathlib import Path
from random import Random
from typing import List

from src.agents import AGENTS
from src.core.config import load_config
from src.core.episode import Episode
from src.core.serialization import write_csv, write_json
from src.core.types import FaultConfig, MonitorDecision, stable_hash
from src.environments.file_ops import FileOpsEnvironment
from src.environments.calendar_ops import CalendarOpsEnvironment
from src.environments.risk_ops import RiskOpsEnvironment
from src.faults import FAULTS
from src.metrics.aggregation import aggregate
from src.monitors.composite import CompositeMonitor

ENVS = {"file_ops": FileOpsEnvironment, "calendar_ops": CalendarOpsEnvironment, "risk_ops": RiskOpsEnvironment}


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
        dynamic = sum(e.execution.success and not e.execution.unsafe and not e.decision.action.abstain for e in shifted) / len(shifted) if shifted else 0.0
        rows.append({"agent_name": agent, "static_score": static, "dynamic_score": dynamic, "gap": static - dynamic, "clean_episodes": len(clean), "shifted_episodes": len(shifted)})
    return rows


def run_eval(config_path: str, seed: int, env: str | None = None, agent: str | None = None, all_envs: bool = False, all_agents: bool = False) -> List[Episode]:
    config = load_config(config_path)
    env_names = list(ENVS) if all_envs else ([env] if env else config.get("environments", ["file_ops"]))
    agent_names = list(AGENTS) if all_agents else ([agent] if agent else config.get("agents", ["naive"]))
    fault_names = config.get("faults", ["normal"])
    fault_severities = config.get("fault_severities", [1.0])
    episodes_per_combo = int(config.get("episodes_per_combo", 3))
    episode_steps = int(config.get("episode_steps", 1))
    run_id = stable_hash({"config": config_path, "seed": seed, "envs": env_names, "agents": agent_names, "faults": fault_names, "severities": fault_severities, "steps": episode_steps}, prefix="run")
    episodes: List[Episode] = []

    for env_name in env_names:
        for agent_name in agent_names:
            for fault_name in fault_names:
                for severity in fault_severities:
                    if fault_name == "normal" and float(severity) != 1.0:
                        continue
                    for i in range(episodes_per_combo):
                        combo_seed = seed + i + len(episodes) * 17
                        rng = Random(combo_seed)
                        env_obj = ENVS[env_name](seed=combo_seed, scenario_index=i)
                        agent_obj = AGENTS[agent_name]()
                        monitor_decisions: List[MonitorDecision] = []
                        step_trace = []
                        final_response = None
                        final_decision = None
                        final_execution = None
                        stop_reason = "max_steps"
                        unsafe_step_count = 0
                        failure_step = ""
                        for step in range(episode_steps):
                            response = env_obj.tool_response()
                            response = FAULTS[fault_name](severity=float(severity)).apply(response, env_obj, rng)
                            decision = agent_obj.decide(env_obj, response)
                            if agent_name == "monitor_gated" and getattr(agent_obj, "last_monitor_decision", None) is not None:
                                monitor_decisions.append(agent_obj.last_monitor_decision)
                            else:
                                monitor_decisions.append(CompositeMonitor().check(env_obj, response.observation, decision.action))
                            execution = env_obj.execute(decision.action, observed_timestamp=response.observation.timestamp)
                            if execution.unsafe:
                                unsafe_step_count += 1
                                failure_step = failure_step or str(step)
                            step_trace.append({
                                "step": step,
                                "tool_response": response.to_dict(),
                                "decision": decision.to_dict(),
                                "execution": execution.to_dict(),
                            })
                            final_response, final_decision, final_execution = response, decision, execution
                            if execution.unsafe:
                                stop_reason = "unsafe_action"
                                break
                            if decision.action.abstain:
                                stop_reason = "abstained"
                                break
                            if execution.success:
                                stop_reason = "success"
                                break
                        recovered = bool(fault_name != "normal" and final_execution and not final_execution.unsafe and (final_decision.action.abstain or any(not m.allow_action for m in monitor_decisions)))
                        meta = {"config_path": config_path, "combo_seed": combo_seed, "episode_steps": episode_steps, "steps_taken": len(step_trace), "multi_step": episode_steps > 1, "unsafe_step_count": unsafe_step_count, "failure_step": failure_step, "stop_reason": stop_reason, "step_trace": step_trace, "recovered": recovered}
                        episodes.append(Episode(env_name, env_obj.scenario_id, agent_name, FaultConfig(fault_name, float(severity)), seed, run_id, final_response, final_decision, monitor_decisions, final_execution, meta))

    write_outputs(episodes, config, seed, run_id)
    return episodes


def write_outputs(episodes: List[Episode], config, seed: int, run_id: str) -> None:
    Path("results").mkdir(exist_ok=True)
    write_csv("results/episode_log.csv", [e.to_row() for e in episodes])
    write_csv("results/summary.csv", aggregate(episodes))
    write_csv("results/static_vs_dynamic.csv", _static_dynamic_rows(episodes))
    with Path("results/multistep_traces.jsonl").open("w", encoding="utf-8") as f:
        for e in episodes:
            f.write(json.dumps({"episode_id": e.episode_id, "step_trace": e.metadata.get("step_trace", [])}, sort_keys=True, default=str) + "\n")
    failure_rows = []
    for e in episodes:
        if e.execution.unsafe:
            fc = e.failure_case()
            monitor_summary = ";".join(r for m in e.monitor_decisions for r in m.reasons)
            failure_rows.append({
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
                "observation_summary": json.dumps(_safe_summary(e.tool_response.observation.data), sort_keys=True, default=str),
                "monitor_summary": monitor_summary,
                "ground_truth_summary": json.dumps(_safe_summary(getattr(ENVS[e.env_name](seed=e.seed), "hidden_ground_truth")()), sort_keys=True, default=str),
                "seed": fc.seed,
                "trace_json": json.dumps(fc.trace, sort_keys=True, default=str),
            })
    write_csv("results/failure_cases.csv", failure_rows, ["case_id", "episode_id", "env_name", "environment", "agent_name", "agent", "fault_name", "fault", "action_type", "unsafe_reasons", "observation_summary", "monitor_summary", "ground_truth_summary", "seed", "trace_json"])
    monitor_rows = []
    for e in episodes:
        for m in e.monitor_decisions:
            monitor_rows.append({
                "episode_id": e.episode_id,
                "env_name": e.env_name,
                "agent_name": e.agent_name,
                "fault_name": e.fault.name,
                "monitor_name": m.monitor_name,
                "allow_action": m.allow_action,
                "risk_score": m.risk_score,
                "reasons": ";".join(m.reasons),
                "metadata_json": json.dumps(m.metadata, sort_keys=True, default=str),
            })
    write_csv("results/monitor_events.csv", monitor_rows)
    write_json("results/config.json", {"seed": seed, "run_id": run_id, "config": config, "episodes": len(episodes)})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Tool-Agent Shift Benchmark")
    parser.add_argument("--config", default="configs/small.yaml")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--env", choices=list(ENVS))
    parser.add_argument("--agent", choices=list(AGENTS))
    parser.add_argument("--all-envs", action="store_true")
    parser.add_argument("--all-agents", action="store_true")
    args = parser.parse_args(argv)
    episodes = run_eval(args.config, args.seed, env=args.env, agent=args.agent, all_envs=args.all_envs, all_agents=args.all_agents)
    print(f"wrote results for {len(episodes)} episodes")


if __name__ == "__main__":
    main()
