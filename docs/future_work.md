# Future Work

The v0.1.0 release already includes multi-step rollouts, fault severity sweeps, an offline LLM-style fixture, monitor ablations, static-vs-dynamic comparison, multi-seed confidence intervals, generated plots, and replayable failures. Future work should extend the benchmark without weakening the safety boundary.

## Higher-fidelity synthetic tasks

- Add richer long-horizon tasks with delayed consequences.
- Add multi-party scheduling tasks with changing priorities.
- Add file workflows where early safe actions can create later unsafe states.
- Add synthetic risk tasks with longer state histories and delayed constraint updates.

## Local and optional model adapters

- Add optional local-model adapters that do not require paid APIs.
- Add fixture-based policy traces for comparing deterministic baseline agents with model-shaped decisions.
- Add clear adapter contracts for users who want to evaluate their own models without committing credentials.

## More realistic shift models

- Add more realistic schema evolution patterns, including nested schema changes and backwards-compatible field additions.
- Add correlated fault patterns where stale state and constraint shift occur together.
- Add latency distributions instead of fixed latency spikes.
- Add richer corrupted-memory cases that distinguish stale cache, wrong cache, and partial cache.

## Oversight and monitor analysis

- Add calibration analysis for monitor risk scores.
- Add threshold sweeps for risk monitors.
- Add per-reason-code precision and recall.
- Add analyses of monitor disagreement and cascading monitor failures.

## Trace and reporting improvements

- Add privacy-preserving trace export for safety monitoring research.
- Add compact HTML reports generated from CSV outputs.
- Add richer failure clustering by reason code and fault family.
- Add release-time validation scripts that check generated artifacts, figures, docs, and archive hygiene.

## External comparison

- Add adapters to compare against other agent-evaluation harnesses while preserving the synthetic-only safety boundary.
- Add a benchmark card format that makes results easier to compare across repositories.
