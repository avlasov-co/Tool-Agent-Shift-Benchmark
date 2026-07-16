from __future__ import annotations

import argparse

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.run_artifacts import resolve_run
from tool_agent_shift_benchmark.reporting.report import generate_markdown_report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate a Markdown report inside an existing run bundle")
    parser.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    run_dir = resolve_run(args.run)
    if run_dir is None:  # pragma: no cover - parser requires a path
        raise RuntimeError("run bundle was not resolved")
    store = ArtifactStore(run_dir)
    output = generate_markdown_report(
        run_dir / "results" / "summary.csv",
        "reports/experimental_report.md",
        artifact_store=store,
    )
    store.finalize(command=["python", "-m", "tool_agent_shift_benchmark.generate_report"])
    print(output)


if __name__ == "__main__":
    main()
