# Tool-Agent Shift Benchmark v0.1.0

Initial release of a deterministic synthetic benchmark for tool-using agent safety under environment shift.

## Included

- Synthetic FileOps, CalendarOps, and RiskOps environments.
- Nine deterministic fault modes: normal, schema drift, stale observation, latency spike, missing field, conflicting tool output, corrupted memory, constraint shift, and compound shift.
- Fault severity sweeps via `fault_severities` in config files.
- Multi-step rollouts via `episode_steps`, including `results/multistep_traces.jsonl`.
- Six agents: naive, retry, validate-then-act, monitor-gated, conservative abstention, and offline LLM-style fixture.
- Offline LLM-style fixture at `src/agents/offline_llm_fixture.py` with policy cases in `fixtures/offline_llm_policy/policy_cases.json`.
- Schema, freshness, consistency, constraint, risk, and composite monitors.
- Monitor ablation configuration in `configs/ablations.yaml`.
- Static-vs-dynamic comparison output at `results/static_vs_dynamic.csv` and plot `figures/static_vs_dynamic_gap.png`.
- Multi-seed confidence interval support via `src/run_seeds.py`, `src/metrics/confidence.py`, and `configs/seeds.yaml`.
- Confidence outputs: `results/seed_summary.csv`, `results/confidence_intervals.csv`, and `figures/confidence_intervals.png`.
- Core outputs: `summary.csv`, `episode_log.csv`, `failure_cases.csv`, `monitor_events.csv`, and `config.json`.
- Plots for unsafe actions, unsafe steps, coverage-vs-safety, monitor recall/precision, recovery, failure breakdown, static-vs-dynamic gap, and confidence intervals.
- Replayable failure cases through `python -m src.reporting.failure_cases --case-id CASE_ID`.
- Tests including `tests/test_multistep_severity_confidence.py`.
- CI, Makefile, reproducibility scripts, paper-style docs, eval card, threat model, limitations, and methodology.

## Reproducibility

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m compileall -q src tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
bash scripts/run_repro.sh
python -m src.run_sweep --config configs/ablations.yaml --seed 42
python -m src.run_seeds --config configs/seeds.yaml --all-envs --all-agents
python -m src.plot_results
python -m src.generate_report
```

## Safety boundary

No real APIs, no real private data, no real filesystem modification, no real calendar systems, no real market APIs, no credentials, no network calls, no exploit code, no bypass guidance, and no external side effects beyond local benchmark outputs.

## Known limitations

The benchmark uses synthetic environments and deterministic baseline agents. Frontier LLM API integration is intentionally excluded from v0.1.0 to avoid paid credentials and unsafe key handling in an open-source repository.
