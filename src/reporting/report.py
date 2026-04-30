from __future__ import annotations
import csv
import json
from pathlib import Path


def _rows(path):
    p = Path(path)
    if not p.exists(): return []
    with p.open("r", encoding="utf-8") as f: return list(csv.DictReader(f))


def generate_markdown_report(summary_path="results/summary.csv", out_path="docs/experimental_report.md"):
    rows = _rows(summary_path); failures = _rows("results/failure_cases.csv"); svd = _rows("results/static_vs_dynamic.csv"); ci = _rows("results/confidence_intervals.csv")
    cfg = {}
    if Path("results/config.json").exists():
        cfg = json.loads(Path("results/config.json").read_text(encoding="utf-8"))
    best = sorted(rows, key=lambda r: (float(r.get("unsafe_action_rate", 0) or 0), -float(r.get("safe_useful_action_rate", 0) or 0)))[:8]
    worst = sorted(rows, key=lambda r: float(r.get("unsafe_action_rate", 0) or 0), reverse=True)[:5]
    lines = ["# Experimental Report", "", "Generated from the current local run outputs.", "", "## Run config", "", f"- Episodes in latest run: {cfg.get('episodes', 'unknown')}", f"- Seed: {cfg.get('seed', 'unknown')}", f"- Run ID: `{cfg.get('run_id', 'unknown')}`", "", "## Summary table", "", "| environment | agent | fault | severity | unsafe | coverage | safe useful |", "|---|---|---|---:|---:|---:|---:|"]
    for r in best:
        lines.append(f"| {r.get('env_name')} | {r.get('agent_name')} | {r.get('fault_name')} | {float(r.get('fault_severity',1) or 1):.2f} | {float(r.get('unsafe_action_rate',0) or 0):.3f} | {float(r.get('coverage',0) or 0):.3f} | {float(r.get('safe_useful_action_rate',0) or 0):.3f} |")
    lines += ["", "## Worst unsafe configurations", ""]
    for r in worst:
        lines.append(f"- {r.get('env_name')} / {r.get('agent_name')} / {r.get('fault_name')} severity {r.get('fault_severity')}: unsafe={float(r.get('unsafe_action_rate',0) or 0):.3f}")
    lines += ["", "## Static vs dynamic gap", ""]
    if svd:
        for r in svd[:8]: lines.append(f"- {r.get('agent_name')}: static={float(r.get('static_score',0) or 0):.3f}, dynamic={float(r.get('dynamic_score',0) or 0):.3f}, gap={float(r.get('gap',0) or 0):.3f}")
    else: lines.append("Static-vs-dynamic output was not generated for this run.")
    lines += ["", "## Confidence intervals", "", f"Confidence interval rows: {len(ci)}", "", "## Representative failure cases", ""]
    for r in failures[:5]: lines.append(f"- `{r.get('case_id')}`: {r.get('env_name')} / {r.get('agent_name')} / {r.get('fault_name')} -> {r.get('unsafe_reasons')}")
    lines += ["", "## Limitations", "", "The benchmark uses synthetic environments and deterministic baseline agents. It does not certify deployed systems. Frontier LLM API integration is intentionally excluded from v0.1.0 to avoid requiring paid credentials or encouraging unsafe key handling in an open-source repository."]
    out = Path(out_path); out.parent.mkdir(parents=True, exist_ok=True); out.write_text("\n".join(lines)+"\n", encoding="utf-8"); return str(out)
