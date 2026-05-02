# Tool-Agent Shift Benchmark: Evaluating Tool-Using Agents Under Environment Shift

## Abstract

Tool-using agents increasingly depend on external state: tool schemas, observations, memory, timestamps, and task constraints. This benchmark evaluates whether agents remain safe and useful when those dependencies become unreliable. It introduces three synthetic environments, nine deterministic fault modes, six agent policies, six monitor types, monitor ablations, multi-step rollouts, fault severity sweeps, static-vs-dynamic comparison, multi-seed confidence intervals, generated plots, and replayable failure cases. The benchmark is intentionally non-operational: it uses synthetic tasks and hidden ground truth to study deployment-style failure mechanisms without touching real APIs, files, calendars, market data, or credentials.

## Introduction

Many agent evaluations test whether a model can complete a task under clean conditions. Real tool-using systems operate in less stable settings. APIs change, observations become stale, fields disappear, tools disagree, memory can become corrupted, latency can make previous state unsafe, and constraints can shift during an episode.

The Tool-Agent Shift Benchmark isolates those failure mechanisms in controlled synthetic environments. The goal is not to certify deployment safety. The goal is to make specific classes of tool-environment failure measurable, reproducible, and inspectable.

## Motivation

A tool-using agent can behave unsafely even when its high-level reasoning is acceptable. If the tool interface changes or the observation is stale, the policy may act on a state that no longer matches hidden ground truth. If constraints shift, an action that appeared safe may become invalid. If monitors only check schemas but not freshness or consistency, oversight can miss failures.

This benchmark treats the tool environment as part of the safety problem. It evaluates agents under faults that target observations, tool outputs, memory, latency, constraints, and monitor decisions.

## Benchmark Design

Each episode has:

1. a hidden ground-truth state maintained by the environment;
2. a visible observation exposed through a synthetic tool interface;
3. an optional fault injection applied only to visible state, memory, constraints, or metadata;
4. an agent decision;
5. an optional monitor decision;
6. an action execution step;
7. a ground-truth safety check;
8. structured logging, metrics, and failure-case export.

Faults must not silently corrupt hidden ground truth. This separation allows the benchmark to determine whether unsafe behavior came from unreliable visible state, agent policy, monitor behavior, or the interaction between them.

## Experimental Matrix

| Dimension | Included |
|---|---|
| Environments | FileOps, CalendarOps, RiskOps |
| Agents | naive, retry, validate-then-act, monitor-gated, conservative, offline LLM-style fixture |
| Fault modes | normal, schema drift, stale observation, latency spike, missing field, conflicting tool output, corrupted memory, constraint shift, compound shift |
| Severity levels | configurable through `fault_severities` |
| Seeds | configurable; `configs/seeds.yaml` includes `[42, 43, 44]` |
| Episode steps | configurable through `episode_steps`; v0.1.0 includes multi-step rollouts |
| Monitor modes | no monitor, schema only, schema + freshness, schema + freshness + consistency, full composite monitor |

The included generated run recorded 162 grouped summary rows and writes detailed traces to `results/episode_log.csv`, `results/failure_cases.csv`, `results/monitor_events.csv`, and `results/multistep_traces.jsonl`.

## Environments

### FileOps

FileOps models synthetic file management. The agent may archive logs, move project files, clean temporary files, and preserve protected files. Unsafe outcomes include deleting or moving protected files, overwriting protected files, acting on stale directory listings, or ignoring hidden protected flags.

### CalendarOps

CalendarOps models synthetic scheduling. The agent must schedule meetings while respecting availability, working hours, timezone offsets, and private metadata boundaries. Unsafe outcomes include double booking, scheduling outside working hours, ignoring timezone constraints, exposing private metadata, or acting on stale availability.

### RiskOps

RiskOps models synthetic exposure control under a toy risk limit. This is not trading and has no real market data. Unsafe outcomes include exceeding a synthetic risk limit, acting on stale state, ignoring volatility spikes, acting with required fields missing, or trusting conflicting snapshots.

## Fault Conditions

| Fault | What it tests |
|---|---|
| `normal` | clean baseline behavior |
| `schema_drift` | renamed or altered fields |
| `stale_observation` | old visible state while hidden ground truth changed |
| `latency_spike` | synthetic latency that increases stale-action risk |
| `missing_field` | removed fields required for safe action |
| `conflicting_tool_output` | contradictory but plausible tool outputs |
| `corrupted_memory` | wrong cached fact or stale previous state |
| `constraint_shift` | visible safety constraints change mid-episode |
| `compound_shift` | multiple faults combined in one episode |

Fault severity is configurable. Severity controls how strongly a fault perturbs visible state or metadata.

## Agent Policies

| Agent | Policy summary |
|---|---|
| `naive` | acts directly on visible tool output |
| `retry` | retries invalid or incomplete outputs before acting |
| `validate_then_act` | checks schema, freshness, and basic constraints |
| `monitor_gated` | uses external monitor output before acting |
| `conservative` | abstains under uncertainty |
| `offline_llm_fixture` | deterministic local fixture approximating model-shaped decisions without API calls |

The offline fixture is intentionally local and deterministic. Frontier LLM API integration is excluded from v0.1.0 to avoid paid credentials and unsafe key handling in an open-source repository.

## Oversight Monitors

The benchmark includes schema, freshness, consistency, constraint, risk, and composite monitors. Monitor decisions include `allow_action`, `risk_score`, `reasons`, `monitor_name`, and metadata. Monitor ablations compare increasing oversight capacity:

| Mode | Included monitors |
|---|---|
| `no_monitor` | no monitor gating |
| `schema_only` | schema monitor |
| `schema_plus_freshness` | schema + freshness |
| `schema_plus_freshness_plus_consistency` | schema + freshness + consistency |
| `full_composite_monitor` | composite monitor stack |

This allows researchers to inspect whether each oversight component improves safety and what coverage or false-positive costs it introduces.

## Metrics

Primary metrics include:

- `task_success_rate`
- `unsafe_action_rate`
- `unsafe_step_rate`
- `constraint_violation_rate`
- `stale_data_action_rate`
- `schema_failure_recovery_rate`
- `monitor_recall`
- `monitor_false_positive_rate`
- `abstention_rate`
- `coverage`
- `recovery_rate`
- `latency_overhead_ms`
- `safe_useful_action_rate`
- `oversight_efficiency`

The benchmark also reports per-fault, per-environment, severity, static-vs-dynamic, and multi-seed confidence outputs.

## Results Summary

The included generated run shows the expected safety/coverage tradeoff:

| Agent | Coverage | Unsafe action rate | Abstention | Safe useful action rate |
|---|---:|---:|---:|---:|
| conservative | 0.333 | 0.000 | 0.667 | 0.333 |
| monitor_gated | 0.333 | 0.000 | 0.667 | 0.333 |
| validate_then_act | 0.333 | 0.000 | 0.667 | 0.333 |
| offline_llm_fixture | 0.333 | 0.111 | 0.667 | 0.222 |
| naive | 0.852 | 0.407 | 0.148 | 0.444 |
| retry | 1.000 | 0.481 | 0.000 | 0.519 |

The table should be interpreted as benchmark evidence, not deployment certification. It shows that acting more often increases useful coverage but also increases unsafe action rate under shift.

## Fault-Level Results

The included run identifies stale observations and compound shifts as the highest-risk fault families:

| Fault | Mean unsafe action rate | Mean safe useful action rate |
|---|---:|---:|
| stale_observation | 0.333 | 0.000 |
| compound_shift | 0.278 | 0.000 |
| latency_spike | 0.167 | 0.667 |
| corrupted_memory | 0.167 | 0.667 |
| conflicting_tool_output | 0.111 | 0.222 |
| constraint_shift | 0.111 | 0.556 |
| missing_field | 0.111 | 0.333 |
| schema_drift | 0.056 | 0.167 |

FileOps had the highest environment-level unsafe action rate in the included run. That is expected because file deletion and move actions create direct protected-file violations under stale or missing metadata.

## Monitor Ablation Results

Monitor ablations are configured in `configs/ablations.yaml` and are run with:

```bash
python -m src.run_sweep --config configs/ablations.yaml --seed 42
```

The ablation modes compare no monitor, schema-only checks, schema plus freshness, schema plus freshness plus consistency, and the full composite monitor. The intended interpretation is not simply whether monitoring reduces unsafe actions, but how much coverage, abstention, latency, and false-positive behavior each level of oversight introduces.

The most important reviewer question is whether additional monitors catch unsafe actions that simpler monitors miss. Schema monitors can detect missing or renamed fields, but they do not fully address stale observations or conflicting tool outputs. Freshness and consistency checks are therefore necessary for deployment-style shift rather than clean static observations.

## Static vs Dynamic Gap

`results/static_vs_dynamic.csv` compares clean isolated behavior with shifted dynamic behavior.

- `static_score`: score on clean observations.
- `dynamic_score`: safe useful action rate across shifted episodes.
- `gap`: static score minus dynamic score.

The included run shows that static behavior can look acceptable while dynamic safety degrades:

| Agent | Static score | Dynamic score | Gap |
|---|---:|---:|---:|
| offline_llm_fixture | 0.667 | 0.167 | 0.500 |
| conservative | 0.667 | 0.292 | 0.375 |
| monitor_gated | 0.667 | 0.292 | 0.375 |
| validate_then_act | 0.667 | 0.292 | 0.375 |
| naive | 0.667 | 0.417 | 0.250 |
| retry | 0.667 | 0.500 | 0.167 |

The gap is the central reason this benchmark exists: clean-task competence is not the same as robust tool-use safety under shifting state.

## Multi-step Failure Propagation

`results/multistep_traces.jsonl` captures how failures propagate across rollout steps. Each trace includes:

- `unsafe_step_count`
- `failure_step`
- `stop_reason`
- `steps_taken`
- `episode_steps`
- `step_trace`

This is useful because many agent failures are not single-decision errors. Early actions can change the state exposed to later steps, and delayed consequences can appear only after multiple interactions.

## Confidence Intervals

The multi-seed runner writes:

- `results/seed_summary.csv`
- `results/confidence_intervals.csv`
- `figures/confidence_intervals.png`

Run it with:

```bash
python -m src.run_seeds --config configs/seeds.yaml --all-envs --all-agents
```

The confidence interval output groups metrics by environment, agent, fault, and metric name. This helps separate stable patterns from single-seed artifacts.

## Representative Failure Cases

Failure cases are exported to `results/failure_cases.csv` and can be inspected with:

```bash
python -m src.reporting.failure_cases --case-id CASE_ID
```

Representative cases include:

1. **FileOps stale listing:** the visible directory listing is stale, while hidden ground truth marks a file as protected. A naive policy acts on the stale listing and triggers a protected-file violation.
2. **CalendarOps stale availability:** the visible availability slot appears open, but hidden ground truth has changed. The action can create a double-booking or working-hour violation.
3. **RiskOps missing volatility or shifted limit:** the visible risk state omits required volatility or presents an outdated limit. Acting on that state can exceed the synthetic risk limit.

A replay shows the environment, fault, observation summary, monitor decision, action taken, hidden safety check, and unsafe reason codes.

## Discussion

The benchmark supports three broad conclusions from the included run.

First, high-coverage agents are more exposed to unsafe actions under shift. The naive and retry agents act frequently, which increases useful actions but also increases unsafe actions.

Second, validation-heavy and monitor-gated agents reduce unsafe behavior by abstaining or blocking risky actions. This improves safety but can reduce task coverage.

Third, dynamic faults produce failures that clean static tests do not reveal. Static-vs-dynamic gaps show why benchmark designs must include changing state, stale observations, and compound faults.

The benchmark does not prove that any policy is safe in deployment. It provides a controlled research scaffold for comparing failure modes and mitigation strategies.

## Limitations

The environments are synthetic and simplified. The agents are deterministic baseline policies, not frontier LLM agents. The offline LLM-style fixture approximates model-shaped decisions without API calls, but it is not a replacement for model evaluation. Metrics are benchmark-specific and should not be treated as universal safety scores. Real deployments require additional validation, security review, monitoring, and domain-specific safety analysis.

## Broader Impact

The benchmark provides a safe way to study tool-agent robustness without real external side effects or private data. It may help researchers design better validation, monitoring, abstention, and recovery mechanisms for tool-using systems.

## Future Work

Future work should focus on richer long-horizon tasks, optional local-model adapters without paid APIs, more realistic schema evolution, monitor calibration analysis, privacy-preserving trace export, and compatibility with other agent-evaluation harnesses.
