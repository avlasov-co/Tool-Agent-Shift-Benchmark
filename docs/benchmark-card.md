# Tool-Agent Shift Benchmark card — v0.4.0

## Purpose and scope

This deterministic synthetic benchmark studies whether tool-using reference
agents remain safe and useful when observations, schemas, freshness, memory,
latency, constraints, and tool outputs shift. It is designed for reproducible
method and infrastructure comparisons, not certification of production agents.

## Evaluation units

Three parameterized environments (`file_ops`, `calendar_ops`, `risk_ops`), five
transparent reference agents, versioned fault schedules, detector compositions,
and independent oversight treatments are crossed over immutable scenario
manifests. Unique scenario manifests—not repeated steps—are the independent
statistical units. Clean and shifted effects use matched scenarios.

## Evidence and metrics

`metric-schema-v2` defines safe success, safe non-success, useful coverage,
abstention, intervention, proposed/executed unsafety, constraint violations,
stale-data actions, failures, incompleteness, budget exhaustion, and ordered
temporal/schema recovery. Every reported rate includes counts, denominator,
formula, inclusion/missing-data rules, schema, and status.

Monitor labels use pure counterfactual risk of the proposed action. Detector
quality is separate from realized hard-gate outcomes. Calibration is reported
only for a score declared probabilistic under `probability-score-v1`.

## Suites and reproducibility

The packaged smoke, standard, research, and challenge contracts are documented
in [golden-suites.md](golden-suites.md). Standard release evidence must be
reproduced twice from a clean sdist installation and compared canonically.
Every bundle must verify as `complete_valid` before reports are generated.

## Intended and prohibited uses

Appropriate uses include deterministic regression testing, metric-method
research, monitor/oversight ablations, failure analysis, and reproducibility
study. Do not use this benchmark alone to claim production safety, frontier
model quality, real-world incident rates, or broad human-impact performance.
Challenge outcomes may not inform development, tuning, thresholds, utility
weights, defaults, or release claims.

## Limitations

Environments and reference policies are synthetic and transparent. Scenario
families cannot cover open-world tool behavior. Some condition cells may have
too few independent scenarios for intervals; those cells are explicitly
refused. Utility analysis depends on declared costs and is not a universal
ranking. See [limitations.md](limitations.md) and the verified per-run reports.
