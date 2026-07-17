"""Reproducible suite performance measurement with explicit budgets."""

from __future__ import annotations

import resource
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.serialization import write_json
from tool_agent_shift_benchmark.core.verification import COMPLETE_VALID, verify_run
from tool_agent_shift_benchmark.run_eval import run_eval
from tool_agent_shift_benchmark.suites import SuiteContract

PERFORMANCE_EVIDENCE_VERSION = "performance-evidence-v1"


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _rss_mib() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # macOS reports bytes; Linux and most BSD-derived CI images report KiB.
    return value / (1024.0 * 1024.0) if sys.platform == "darwin" else value / 1024.0


def _measure_once(contract: SuiteContract, root: Path, workers: int) -> dict[str, Any]:
    run_dir = root / f"workers-{workers}"
    store = ArtifactStore(run_dir)
    tracemalloc.start()
    started = time.perf_counter()
    episodes = run_eval(contract.config, contract.seed, workers=workers, artifact_store=store)
    duration = time.perf_counter() - started
    _current, python_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    store.finalize(command=["tasb", "performance", "--suite", contract.name, "--workers", str(workers)])
    verification = verify_run(run_dir)
    return {
        "workers": workers,
        "episodes": len(episodes),
        "runtime_seconds": round(duration, 6),
        "episodes_per_second": round(len(episodes) / duration, 6),
        "python_allocation_peak_mib": round(python_peak / (1024.0 * 1024.0), 6),
        "process_peak_rss_mib": round(_rss_mib(), 6),
        "artifact_size_mib": round(_directory_size(run_dir) / (1024.0 * 1024.0), 6),
        "verification_status": verification["status"],
    }


def measure_suite_performance(contract: SuiteContract, *, output: str | Path) -> dict[str, Any]:
    """Measure one- and two-worker executions in an isolated temporary root."""

    with tempfile.TemporaryDirectory(prefix="tasb-performance-") as temp:
        root = Path(temp)
        measurements = [_measure_once(contract, root, workers) for workers in (1, 2)]
    single, parallel = measurements
    scaling_ratio = parallel["runtime_seconds"] / single["runtime_seconds"]
    budgets = dict(contract.performance_budget)
    checks = {
        "runtime": single["runtime_seconds"] <= budgets["runtime_seconds_max"],
        "process_peak_memory": max(row["process_peak_rss_mib"] for row in measurements)
        <= budgets["peak_memory_mib_max"],
        "artifact_size": max(row["artifact_size_mib"] for row in measurements) <= budgets["artifact_size_mib_max"],
        "worker_scaling": scaling_ratio <= budgets["worker_scaling_ratio_max"],
        "bundle_verification": all(row["verification_status"] == COMPLETE_VALID for row in measurements),
    }
    report = {
        "schema_version": PERFORMANCE_EVIDENCE_VERSION,
        "suite": contract.name,
        "suite_version": contract.suite_version,
        "measurement_method": {
            "runtime": "time.perf_counter around deterministic evaluation",
            "memory": "process peak RSS plus Python tracemalloc allocation peak",
            "artifact_size": "sum of finalized run-bundle file sizes",
            "worker_scaling": "two-worker runtime divided by one-worker runtime; lower is better",
        },
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "measurements": measurements,
        "worker_scaling_ratio": round(scaling_ratio, 6),
        "budgets": budgets,
        "regression_policy": {
            "relative_runtime_regression_fraction_max": budgets["runtime_regression_fraction_max"],
            "comparison_requires_same suite_version, Python minor version, OS, and CPU class": True,
        },
        "checks": checks,
        "status": "passed" if all(checks.values()) else "failed",
    }
    write_json(output, report)
    return report
