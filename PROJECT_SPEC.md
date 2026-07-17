# Tool-Agent Shift Benchmark — Project Specification

The current runtime architecture is documented in [docs/architecture.svg](docs/architecture.svg), generated from [docs/architecture.mmd](docs/architecture.mmd).

## Research question

Do tool-using AI agents remain safe and useful when their tools, observations, memory, and constraints become unreliable?

## Thesis

Agents do not only fail because they reason badly. They also fail because the surrounding tool environment shifts: schemas drift, observations become stale, fields disappear, tools disagree, memory corrupts, latency makes old data dangerous, and constraints change while the agent continues acting as if reality politely waited for it. It does not. Reality is rude like that.

This benchmark isolates those mechanisms in safe synthetic environments with hidden ground truth, deterministic fault injection, replayable traces, and measurable outcomes.

## Why synthetic but realistic examples are valuable

The benchmark uses synthetic environments because real APIs, private user data, real calendars, financial systems, exploit targets, or credentials would turn an evaluation artifact into a liability carnival. Synthetic settings allow:

- hidden ground truth for exact safety checks;
- controlled shifts with deterministic seeds;
- repeatable experiments across agents and monitors;
- replayable failure cases;
- safe publication without real external side effects.

The scenarios are intentionally non-operational but model real classes of failure in tool-using systems.

## Safety boundary

This repository contains no real network calls, no real file-system modification outside its own synthetic outputs, no real calendar APIs, no real market APIs, no credentials, no real private user data, no exploit code, no bypass guidance, no operational abuse instructions, and no financial advice. RiskOps is a toy synthetic risk-control environment only.

## Scope

The benchmark measures agent behavior under observation/tool/memory/constraint shift across three synthetic environments:

1. **FileOps**: synthetic file-management with protected files.
2. **CalendarOps**: synthetic scheduling with availability, timezones, and working-hour constraints.
3. **RiskOps**: synthetic exposure management with toy market state and risk limits.

## Non-goals

- Measuring frontier-model reasoning ability directly.
- Calling LLM APIs.
- Modeling real trading or giving financial advice.
- Testing real calendars, user files, or production systems.
- Providing exploit or bypass techniques.
- Claiming that synthetic results directly transfer to deployed agents without validation.

## Success, abstention, recovery, and ground truth

- **Ground truth** is the hidden environment state used only by the evaluator to judge safety and success. Faults never mutate it.
- **Success** means completing the assigned synthetic task without unsafe action or constraint violation.
- **Unsafe action** means an action that violates hidden ground truth or environment safety rules.
- **Abstention** means the agent deliberately refuses to act under uncertainty.
- **Recovery** means a policy avoids or repairs a fault-induced bad decision through retry, validation, monitor blocking, or abstention.

## Environments

### FileOps

Tasks: archive old logs, move project files, clean temporary files, preserve protected files.

Unsafe actions: delete protected file, overwrite protected file, move wrong file, act on stale directory listing, ignore hidden protected flag.

### CalendarOps

Tasks: schedule meetings, avoid conflicts, respect availability, respect timezone and working-hour constraints.

Unsafe actions: double-book attendee, schedule outside allowed hours, ignore timezone constraint, expose private calendar metadata, act on stale availability.

### RiskOps

Tasks: keep synthetic exposure under risk limit, react to synthetic market state, avoid acting under stale or incomplete state.

Unsafe actions: exceed synthetic risk limit, act on stale synthetic market state, ignore volatility spike, act when required risk fields are missing, trust conflicting synthetic snapshots.

## Faults

- normal: no-op baseline.
- schema_drift: renames or restructures fields.
- stale_observation: ages timestamps or returns older snapshots.
- latency_spike: adds deterministic latency metadata.
- missing_field: removes required fields.
- conflicting_tool_output: adds disagreement between state views.
- corrupted_memory: modifies agent memory-like hints.
- constraint_shift: changes visible constraints without mutating hidden truth.
- compound_shift: combines multiple faults.

## Agents

- **NaiveAgent**: acts directly on tool output. High coverage, weak safety.
- **RetryAgent**: retries invalid or incomplete outputs before acting.
- **ValidateThenActAgent**: checks schema, freshness, and visible constraints before acting.
- **MonitorGatedAgent**: asks external monitors before acting.
- **ConservativeAbstentionAgent**: abstains under uncertainty. Low unsafe action rate, lower coverage.

## Monitors

- **SchemaMonitor**: detects missing fields, renamed fields, invalid types.
- **FreshnessMonitor**: detects stale observations and old timestamps.
- **ConsistencyMonitor**: detects disagreement between tool outputs or state views.
- **ConstraintMonitor**: detects action constraint violations.
- **RiskMonitor**: aggregates safety risk signals.
- **CompositeMonitor**: combines monitor decisions into allow/block/abstain.

Every monitor decision includes allow_action, risk_score, reasons, monitor_name, and metadata.

## Metrics

- safe_success_rate
- safe_non_success_rate
- unsafe_proposed_action_rate
- unsafe_executed_action_rate
- constraint_violation_rate
- stale_data_action_rate
- temporal_recovery_rate
- schema_recovery_rate
- monitor TP/FP/TN/FN, precision, recall, specificity, FPR, and FNR
- agent_abstention_rate
- useful_action_rate
- oversight_intervention_rate
- latency_overhead_ms
- orchestration_failure_rate

## Pre-registered diagnostic hypotheses

These are hypotheses to test, not claims: direct-action policies may retain more
coverage and proposal harm under shift; conservative policies may trade coverage
for abstention; hard-gate oversight may reduce executed harm while introducing
unnecessary blocks; validation may improve schema/freshness outcomes. Reports
must link any supported statement to verified artifacts and uncertainty.
- Compound shifts should produce the highest failure rate.

## Repository file tree

```text
tool-agent-shift-benchmark
├── README.md
├── LICENSE
├── CITATION.cff
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── pyproject.toml
├── requirements/
│   ├── runtime.txt
│   └── development.txt
├── Makefile
├── PROJECT_SPEC.md
├── docs
│   ├── index.md
│   ├── paper.md
│   ├── eval_card.md
│   ├── threat_model.md
│   ├── methodology.md
│   ├── limitations.md
│   ├── reproducibility.md
│   ├── failure_taxonomy.md
│   ├── safety_case.md
│   └── future_work.md
├── figures
│   └── .gitkeep
├── results
│   └── .gitkeep
├── scripts
│   ├── run_repro.sh
│   └── clean_outputs.sh
├── src
│   └── tool_agent_shift_benchmark
│       ├── agents, analysis, core, environments, faults, metrics, monitors,
│       │   reporting, and tools
│       ├── run_eval.py, run_seeds.py, and run_sweep.py
│       └── resources
│           ├── configs
│           ├── policies
│           └── templates
├── tests
│   ├── test_core_types.py
│   ├── test_environments.py
│   ├── test_faults.py
│   ├── test_agents.py
│   ├── test_monitors.py
│   ├── test_metrics.py
│   ├── test_reproducibility.py
│   └── test_reporting.py
└── .github
    └── workflows
        └── ci.yml
```

## Architecture flow

```text
Scenario / Synthetic Task
        ↓
Environment
        ↓
Tool Interface
        ↓
Fault Injection
        ↓
Agent Decision
        ↓
Monitor Decision
        ↓
Action Execution
        ↓
Ground Truth Safety Check
        ↓
Metrics + Logs + Failure Cases
        ↓
Plots + Report + Paper-Style Analysis
```

## Release criteria

A release is acceptable only when:

- tests pass;
- small benchmark runs from a fresh clone;
- results and plots are generated;
- failure cases are replayable;
- README explains the project quickly;
- paper-style report exists;
- safety boundary is explicit;
- no private data, real APIs, credentials, or dangerous operational content are present;
- LICENSE and CITATION.cff are present;
- release archives and SHA256 checksums are generated.

## Implementation order

1. Specification and architecture.
2. Core typed records and deterministic IDs.
3. FileOps, basic faults, NaiveAgent, basic metrics.
4. Monitors.
5. Full agent set.
6. CalendarOps and RiskOps.
7. Full fault system and sweeps.
8. Metrics, plots, reporting, failure replay.
9. Documentation and research packaging.
10. CI, Makefile, reproducibility scripts, final validation.

## v0.4.0 evidence design

The current design includes multi-step rollouts, fault severity sweeps, a deterministic offline fixture, clean-versus-shifted comparison, typed metric evidence, and scenario-clustered intervals. See the metric data dictionary and run-bundle artifact manifest.

Frontier LLM API integration remains out of scope for v0.4.0 evidence because the benchmark must remain open-source, reproducible, and free from paid credential requirements.
