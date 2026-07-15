from __future__ import annotations
import csv
import json
from pathlib import Path
from src.core.episode import Episode
from src.metrics.aggregation import aggregate


def _rows(path):
    p = Path(path)
    if not p.exists() and p.name == "summary.csv":
        structured = p.parent / "episodes.jsonl"
        if structured.exists():
            episodes = [Episode.from_dict(json.loads(line)) for line in structured.read_text(encoding="utf-8").splitlines() if line.strip()]
            return aggregate(episodes)
    if not p.exists(): return []
    with p.open("r", encoding="utf-8") as f: return list(csv.DictReader(f))


def generate_markdown_report(summary_path="results/summary.csv", out_path="docs/experimental_report.md"):
    results_dir = Path(summary_path).parent
    rows = _rows(summary_path); failures = _rows(results_dir / "failure_cases.csv"); svd = _rows(results_dir / "static_vs_dynamic.csv"); ci = _rows(results_dir / "confidence_intervals.csv")
    cfg = {}
    config_path = results_dir / "config.json"
    if config_path.exists():
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    best = sorted(rows, key=lambda r: (float(r.get("unsafe_action_rate", 0) or 0), -float(r.get("safe_useful_action_rate", 0) or 0)))[:8]
    worst = sorted(rows, key=lambda r: float(r.get("unsafe_action_rate", 0) or 0), reverse=True)[:5]
    lines = ["# Experimental Report", "", "Generated from the current local run outputs.", "", "## Run config", "", f"- Episodes in latest run: {cfg.get('episodes', 'unknown')}", f"- Seed: {cfg.get('seed', 'unknown')}", f"- Run ID: `{cfg.get('run_id', 'unknown')}`", "", "## Summary table", "", "| environment | agent | fault | severity | unsafe | coverage | safe useful |", "|---|---|---|---:|---:|---:|---:|"]
    for r in best:
        lines.append(f"| {r.get('env_name')} | {r.get('agent_name')} | {r.get('fault_name')} | {float(r.get('fault_severity',1) or 1):.2f} | {float(r.get('unsafe_action_rate',0) or 0):.3f} | {float(r.get('coverage',0) or 0):.3f} | {float(r.get('safe_useful_action_rate',0) or 0):.3f} |")
    lines += ["", "## Worst unsafe configurations", ""]
    for r in worst:
        lines.append(f"- {r.get('env_name')} / {r.get('agent_name')} / {r.get('fault_name')} severity {r.get('fault_severity')}: unsafe={float(r.get('unsafe_action_rate',0) or 0):.3f}")
    lines += ["", "## How to read the charts", "", "The figures are designed to answer one question each:", "", "- **Unsafe action rate / constraint violation rate / unsafe step rate:** lower values mean fewer unsafe decisions. Episode-level violation rate counts whether an episode failed at least once; step rate measures how often unsafe behavior occurred across the rollout.", "- **Coverage vs. safety:** each point is one configuration. Points farther right complete more useful work; points higher up have a higher safe-action rate. The desirable region is the upper-right corner.", "- **Monitor recall:** higher values mean the monitor catches more genuinely unsafe cases. Recall alone does not show false alarms, so read it with coverage and precision.", "- **Recovery rate:** higher values mean the agent can return to a safe, useful trajectory after the environment shifts.", "- **Static vs. dynamic performance gap:** the gap shows how much behavior changes when the agent must act over multiple steps rather than answer from a fixed snapshot.", "- **Risk calibration error:** lower values mean predicted risk better matches observed unsafe behavior.", "- **Compound-shift effect:** positive values mean two simultaneous faults are more damaging than the worst single fault.", "", "## Static vs dynamic gap", ""]
    if svd:
        for r in svd[:8]: lines.append(f"- {r.get('agent_name')}: static={float(r.get('static_score',0) or 0):.3f}, dynamic={float(r.get('dynamic_score',0) or 0):.3f}, gap={float(r.get('gap',0) or 0):.3f}")
    else: lines.append("Static-vs-dynamic output was not generated for this run.")
    lines += ["", "## Confidence intervals", "", f"Confidence interval rows: {len(ci)}", "", "## Representative failure cases", ""]
    for r in failures[:5]: lines.append(f"- `{r.get('case_id')}`: {r.get('env_name')} / {r.get('agent_name')} / {r.get('fault_name')} -> {r.get('unsafe_reasons')}")
    lines += ["", "## Limitations", "", "The benchmark uses synthetic environments and deterministic baseline agents. It does not certify deployed systems. Frontier LLM API integration is intentionally excluded from v0.1.0 to avoid requiring paid credentials or encouraging unsafe key handling in an open-source repository."]
    out = Path(out_path); out.parent.mkdir(parents=True, exist_ok=True); out.write_text("\n".join(lines)+"\n", encoding="utf-8"); return str(out)
