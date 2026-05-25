from __future__ import annotations

import argparse
import csv
from pathlib import Path
from src.core.config import load_config
from src.core.serialization import write_csv
from src.metrics.confidence import confidence_intervals
from src.run_eval import run_eval


def _read_rows(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_seeds(config_path: str, all_envs: bool = False, all_agents: bool = False):
    cfg = load_config(config_path)
    seeds = [int(s) for s in cfg.get("seeds", [42, 43, 44])]
    seed_rows = []
    for seed in seeds:
        run_eval(config_path, seed=seed, all_envs=all_envs, all_agents=all_agents)
        for row in _read_rows("results/summary.csv"):
            row = dict(row)
            row["seed"] = seed
            seed_rows.append(row)
    Path("results").mkdir(exist_ok=True)
    write_csv("results/seed_summary.csv", seed_rows)
    ci_rows = confidence_intervals(seed_rows)
    write_csv("results/confidence_intervals.csv", ci_rows)
    return seed_rows, ci_rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run multi-seed Tool-Agent Shift Benchmark")
    parser.add_argument("--config", default="configs/seeds.yaml")
    parser.add_argument("--all-envs", action="store_true")
    parser.add_argument("--all-agents", action="store_true")
    args = parser.parse_args(argv)
    seed_rows, ci_rows = run_seeds(args.config, all_envs=args.all_envs, all_agents=args.all_agents)
    print(f"multi-seed episodes: {sum(int(float(r.get('episodes', 0))) for r in seed_rows)}; seed rows: {len(seed_rows)}; ci rows: {len(ci_rows)}")


if __name__ == "__main__":
    main()
