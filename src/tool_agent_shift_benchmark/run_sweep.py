from __future__ import annotations

import argparse

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.run_artifacts import prepare_run_dir
from tool_agent_shift_benchmark.run_eval import run_eval


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run benchmark sweep")
    parser.add_argument("--config", default="ablations")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-name")
    args = parser.parse_args(argv)
    store = ArtifactStore(prepare_run_dir(args.run_name))
    episodes = run_eval(args.config, args.seed, all_envs=True, all_agents=True, artifact_store=store)
    store.finalize(command=["python", "-m", "tool_agent_shift_benchmark.run_sweep"])
    print(f"sweep complete: {len(episodes)} episodes")


if __name__ == "__main__":
    main()
