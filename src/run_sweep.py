from __future__ import annotations
import argparse
from src.run_eval import run_eval


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run benchmark sweep")
    parser.add_argument("--config", default="configs/ablations.yaml")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    episodes = run_eval(args.config, args.seed, all_envs=True, all_agents=True)
    print(f"sweep complete: {len(episodes)} episodes")

if __name__ == "__main__":
    main()
