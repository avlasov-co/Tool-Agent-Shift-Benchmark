from __future__ import annotations

import argparse

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.run_artifacts import resolve_run
from tool_agent_shift_benchmark.reporting.plots import generate_plots


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate plots inside an existing run bundle")
    parser.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    run_dir = resolve_run(args.run)
    if run_dir is None:  # pragma: no cover - parser requires a path
        raise RuntimeError("run bundle was not resolved")
    store = ArtifactStore(run_dir)
    plots = generate_plots(
        run_dir / "results" / "summary.csv",
        "plots",
        results_dir=run_dir / "results",
        artifact_store=store,
    )
    store.finalize(command=["python", "-m", "tool_agent_shift_benchmark.plot_results"])
    print("generated plots:")
    for p in plots:
        print(p)


if __name__ == "__main__":
    main()
