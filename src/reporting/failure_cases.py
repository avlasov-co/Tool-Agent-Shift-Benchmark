from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from src.core.serialization import canonical_dumps, canonical_loads


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _cluster_lookup(case_id: str, analysis_dir: str | Path = "results/analysis") -> dict[str, Any]:
    analysis = Path(analysis_dir)
    examples = []
    examples_path = analysis / "failure_cluster_examples.jsonl"
    if examples_path.exists():
        with examples_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    examples.append(canonical_loads(line))
    cluster_id = ""
    for item in examples:
        if item.get("case_id") == case_id:
            cluster_id = str(item.get("cluster_id", ""))
            break
    if not cluster_id:
        return {"cluster_id": "", "similar_cases": []}
    similar = [
        item.get("case_id")
        for item in examples
        if item.get("cluster_id") == cluster_id and item.get("case_id") != case_id
    ]
    return {"cluster_id": cluster_id, "similar_cases": [c for c in similar if c][:5]}


def replay_case(
    case_id: str,
    path: str = "results/failure_cases.csv",
    analysis_dir: str | Path = "results/analysis",
) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    for row in _read_csv(p):
        if row.get("case_id") == case_id:
            trace = canonical_loads(row.get("trace_json") or "{}")
            cluster = _cluster_lookup(case_id, analysis_dir)
            return {
                "case_id": case_id,
                "episode_id": row.get("episode_id", ""),
                "environment": row.get("environment") or row.get("env_name", ""),
                "agent": row.get("agent") or row.get("agent_name", ""),
                "fault": row.get("fault") or row.get("fault_name", ""),
                "action_type": row.get("action_type", ""),
                "unsafe_reasons": row.get("unsafe_reasons", ""),
                "monitor_summary": row.get("monitor_summary", ""),
                "observation_summary": row.get("observation_summary", ""),
                "ground_truth_summary": row.get("ground_truth_summary", ""),
                "cluster_id": cluster["cluster_id"],
                "similar_cases": cluster["similar_cases"],
                "trace": trace,
            }
    raise KeyError(f"case not found: {case_id}")


def format_replay(data: dict[str, Any], fmt: str = "json") -> str:
    if fmt == "json":
        return canonical_dumps(data, pretty=True)
    if fmt == "markdown":
        lines = [
            f"# Failure replay: `{data['case_id']}`",
            "",
            f"- Episode: `{data.get('episode_id', '')}`",
            f"- Environment: `{data.get('environment', '')}`",
            f"- Agent: `{data.get('agent', '')}`",
            f"- Fault: `{data.get('fault', '')}`",
            f"- Action: `{data.get('action_type', '')}`",
            f"- Unsafe reasons: `{data.get('unsafe_reasons', '')}`",
            f"- Failure cluster: `{data.get('cluster_id', '') or 'not available'}`",
            f"- Similar cases: `{';'.join(data.get('similar_cases', [])) or 'none'}`",
            "",
            "## Monitor summary",
            "",
            data.get("monitor_summary", "") or "No monitor summary recorded.",
            "",
            "## Visible observation summary",
            "",
            "```json",
            data.get("observation_summary", "") or "{}",
            "```",
            "",
            "## Hidden evaluator summary",
            "",
            "```json",
            data.get("ground_truth_summary", "") or "{}",
            "```",
        ]
        return "\n".join(lines)
    if fmt == "text":
        return "\n".join(
            [
                f"case_id: {data.get('case_id', '')}",
                f"episode_id: {data.get('episode_id', '')}",
                f"environment: {data.get('environment', '')}",
                f"agent: {data.get('agent', '')}",
                f"fault: {data.get('fault', '')}",
                f"action_type: {data.get('action_type', '')}",
                f"unsafe_reasons: {data.get('unsafe_reasons', '')}",
                f"cluster_id: {data.get('cluster_id', '')}",
                f"similar_cases: {';'.join(data.get('similar_cases', []))}",
            ]
        )
    raise ValueError(f"unsupported replay format: {fmt}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Replay a recorded failure case")
    parser.add_argument("case_id", nargs="?")
    parser.add_argument("--case-id", dest="case_id_flag")
    parser.add_argument("--path", default="results/failure_cases.csv")
    parser.add_argument("--analysis-dir", default="results/analysis")
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="json")
    args = parser.parse_args(argv)
    case_id = args.case_id_flag or args.case_id
    if not case_id:
        parser.error("case id required")
    print(format_replay(replay_case(case_id, args.path, args.analysis_dir), args.format))


if __name__ == "__main__":
    main()
