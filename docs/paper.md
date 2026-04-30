# Tool-Agent Shift Benchmark: Evaluating Tool-Using Agents Under Environment Shift

## Abstract

Tool-using agents increasingly depend on external observations, schemas, memory, and constraints. This benchmark evaluates whether agents remain safe and useful when those dependencies become unreliable. We introduce three synthetic environments, nine fault conditions, five agent policies, six monitors, reproducible metrics, plots, and replayable failure cases. The benchmark is intentionally non-operational but designed to model realistic classes of tool-agent failure.

## Introduction

Tool use gives agents reach. Reach also gives them more ways to make mistakes at machine speed, because apparently giving software more buttons was not exciting enough. The benchmark studies failures caused by environmental shift rather than only poor reasoning.

## Motivation

Real deployments face API drift, stale observations, missing fields, conflicting tools, corrupted memory, latency, and changing constraints. These failures can make an otherwise competent agent unsafe.

## Benchmark Design

Each episode has a hidden ground truth, a visible tool observation, optional fault injection, agent decision, monitor decision, action execution, and metrics logging. Faults mutate only observations, visible constraints, or metadata, never hidden ground truth.

## Environments

FileOps models synthetic file management with protected files. CalendarOps models synthetic scheduling with availability and timezone constraints. RiskOps models toy synthetic exposure control under risk limits.

## Fault Conditions

The benchmark includes normal, schema drift, stale observation, latency spike, missing field, conflicting tool output, corrupted memory, constraint shift, and compound shift.

## Agent Policies

NaiveAgent acts directly. RetryAgent retries invalid outputs. ValidateThenActAgent validates schema and freshness. MonitorGatedAgent uses oversight monitors. ConservativeAbstentionAgent abstains under uncertainty.

## Oversight Monitors

Schema, freshness, consistency, constraint, risk, and composite monitors emit structured allow/block decisions, risk scores, and reason codes.

## Metrics

Metrics include task success, unsafe action rate, constraint violation rate, stale-data action rate, schema recovery, monitor recall, false positives, abstention, coverage, recovery, latency overhead, safe useful action rate, and oversight efficiency.

## Experiments

Run `python -m src.run_eval --config configs/default.yaml --seed 42`, then generate plots and reports.

## Results

Results are generated locally into `results/summary.csv` and `docs/experimental_report.md`. Expected patterns are high naive coverage with more failures, lower conservative failure with more abstention, and monitor-gated middle-ground behavior.

## Failure Analysis

Failure cases are stored in `results/failure_cases.csv` and can be replayed with `python -m src.reporting.failure_cases --case-id CASE_ID`.

## Limitations

The benchmark is synthetic. It cannot prove real deployment safety. It isolates mechanisms and supports controlled comparisons.

## Broader Impact

The benchmark helps researchers evaluate tool-agent robustness safely without real external side effects or private data.

## Future Work

Future versions should include richer multi-step tasks, more realistic schema evolution, calibrated severity controls, and LLM-in-the-loop adapters that preserve the safety boundary.

## v0.1.0 extended release additions

This release includes multi-step rollouts, fault severity sweeps, a deterministic offline LLM-style fixture agent, static-vs-dynamic comparison, and multi-seed confidence intervals. The relevant files are `src/run_seeds.py`, `src/metrics/confidence.py`, `configs/seeds.yaml`, `src/agents/offline_llm_fixture.py`, `fixtures/offline_llm_policy/policy_cases.json`, and `tests/test_multistep_severity_confidence.py`.

Frontier LLM API integration is intentionally out of scope for v0.1.0 because the benchmark must remain open-source, reproducible, and free from paid credential requirements.
