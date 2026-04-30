from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path


def replay_case(case_id: str, path: str = "results/failure_cases.csv") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    with p.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("case_id") == case_id:
                trace = json.loads(row["trace_json"])
                return {"case_id": case_id, "trace": trace, "unsafe_reasons": row.get("unsafe_reasons", "")}
    raise KeyError(f"case not found: {case_id}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Replay a recorded failure case")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--path", default="results/failure_cases.csv")
    args = parser.parse_args(argv)
    print(json.dumps(replay_case(args.case_id, args.path), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
