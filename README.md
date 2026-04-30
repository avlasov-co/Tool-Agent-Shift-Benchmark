# Tool-Agent Shift Benchmark

A deterministic benchmark for evaluating whether tool-using agents remain safe and useful when tools, observations, memory, and constraints become unreliable.

## 30-second version

Modern agents can fail even when their reasoning is decent because the tool world around them changes. APIs drift. Fields vanish. Observations become stale. Tools disagree. Constraints shift. Then the agent confidently acts anyway, because apparently confidence is free.

This repository provides safe synthetic environments, deterministic fault injection, multiple agent policies, oversight monitors, metrics, plots, replayable failures, and a paper-style report.

## Safety boundary

This project is non-operational by design:

- no real APIs;
- no real user files;
- no real calendar systems;
- no real market data;
- no credentials;
- no network calls;
- no exploit code;
- no financial advice;
- no external side effects beyond writing benchmark outputs under `results/` and `figures/`.

## Install

```bash
git clone <repo-url>
cd tool-agent-shift-benchmark
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick start

```bash
python -m src.run_eval --config configs/small.yaml --seed 42
python -m src.plot_results
python -m src.generate_report
```

## Reproduce the small benchmark

```bash
bash scripts/run_repro.sh
```

## Main outputs

- `results/summary.csv` — grouped metrics by environment, agent, and fault.
- `results/episode_log.csv` — per-episode trace summary.
- `results/failure_cases.csv` — replayable unsafe cases.
- `results/monitor_events.csv` — monitor decisions and reason codes.
- `results/config.json` — exact run metadata.
- `figures/*.png` — benchmark plots.
- `docs/experimental_report.md` — generated report from current results.

## Main metrics

- `unsafe_action_rate`: fraction of episodes with unsafe actions.
- `coverage`: fraction of episodes where an agent took a non-abstain action.
- `abstention_rate`: fraction of episodes where the agent abstained.
- `task_success_rate`: safe task completion rate.
- `safe_useful_action_rate`: useful successful action rate without unsafe behavior.
- `monitor_recall`: how often monitor gating caught unsafe actions.
- `monitor_false_positive_rate`: how often monitor gating blocked safe actions.

## Repository map

```text
tool-agent-shift-benchmark
├── README.md
├── LICENSE
├── CITATION.cff
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── pyproject.toml
├── requirements.txt
├── Makefile
├── PROJECT_SPEC.md
├── configs
│   ├── small.yaml
│   ├── default.yaml
│   ├── full.yaml
│   └── ablations.yaml
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
│   ├── __init__.py
│   ├── run_eval.py
│   ├── run_sweep.py
│   ├── plot_results.py
│   ├── generate_report.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── types.py
│   │   ├── episode.py
│   │   ├── registry.py
│   │   ├── config.py
│   │   └── serialization.py
│   ├── environments
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── file_ops.py
│   │   ├── calendar_ops.py
│   │   └── risk_ops.py
│   ├── tools
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── file_tools.py
│   │   ├── calendar_tools.py
│   │   └── market_tools.py
│   ├── faults
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── schema_drift.py
│   │   ├── stale_observation.py
│   │   ├── latency_spike.py
│   │   ├── missing_field.py
│   │   ├── conflicting_output.py
│   │   ├── corrupted_memory.py
│   │   ├── constraint_shift.py
│   │   └── compound.py
│   ├── agents
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── naive.py
│   │   ├── retry.py
│   │   ├── validate_then_act.py
│   │   ├── monitor_gated.py
│   │   └── conservative.py
│   ├── monitors
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── schema.py
│   │   ├── freshness.py
│   │   ├── consistency.py
│   │   ├── constraint.py
│   │   ├── risk.py
│   │   └── composite.py
│   ├── metrics
│   │   ├── __init__.py
│   │   ├── safety.py
│   │   ├── coverage.py
│   │   ├── monitors.py
│   │   └── aggregation.py
│   └── reporting
│       ├── __init__.py
│       ├── plots.py
│       ├── report.py
│       └── failure_cases.py
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
User Task / Scenario
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
Outcome + Unsafe Action Check
        ↓
Metrics / Logging / Failure Cases
        ↓
Plots / Report / Final Results
```

## What this benchmark measures

It measures controlled failure modes caused by synthetic tool-environment shift: stale data, schema drift, missing fields, conflicting outputs, corrupted memory, latency, and shifting constraints.

## What it does not measure

It does not measure real-world deployment safety directly, real trading, real scheduling, real filesystem safety, or frontier-model capability. It is an evaluation scaffold for isolating failure mechanisms under controlled conditions.

## Citation

See `CITATION.cff`.

## v0.1.0 extended release additions

This release includes multi-step rollouts, fault severity sweeps, a deterministic offline LLM-style fixture agent, static-vs-dynamic comparison, and multi-seed confidence intervals. The relevant files are `src/run_seeds.py`, `src/metrics/confidence.py`, `configs/seeds.yaml`, `src/agents/offline_llm_fixture.py`, `fixtures/offline_llm_policy/policy_cases.json`, and `tests/test_multistep_severity_confidence.py`.

Frontier LLM API integration is intentionally out of scope for v0.1.0 because the benchmark must remain open-source, reproducible, and free from paid credential requirements.
