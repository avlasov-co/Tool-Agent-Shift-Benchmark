# Agent and Monitor Boundary

The benchmark now passes agents and monitors an `ObservationContext`, not the full synthetic environment object.

This is a benchmark-validity guardrail. Agents and monitors can inspect only:

- the current environment name and scenario id;
- the visible observation returned by the tool after fault injection;
- visible constraints attached to that observation;
- visible schema requirements;
- the benchmark's current timestamp;
- helper methods that propose or validate actions using visible observation data only.

They cannot access:

- `hidden_ground_truth()`;
- `execute()`;
- unfaulted `tool_response()` calls after a fault has been applied;
- private environment fields such as hidden protected files, hidden meetings, or hidden market state;
- post-hoc unsafe labels or metric outputs.

## Why this matters

The evaluator owns hidden ground truth. The policy being evaluated should not see it, otherwise the benchmark measures leakage, not robustness. A real deployed tool agent usually sees a tool response, task constraints, timestamps, and maybe schema metadata. It does not get a perfect clean copy of the world after the shifted observation has already failed.

## Visible validation vs hidden scoring

`ObservationContext.validate_action(...)` performs visible-only checks. It can catch things visible in the observation, such as a visible protected file flag, visible working-hours mismatch, or visible risk-limit violation. It intentionally cannot catch hidden-only hazards.

The synthetic environment still performs hidden scoring through `execute(...)` after the agent decision. That is where evaluator-only facts are allowed to determine whether an action was unsafe.

This means a monitor may allow an action that looks safe from visible data, while the hidden evaluator later marks it unsafe. That is not a bug. That is the point of testing agents under stale, missing, conflicting, or shifted observations.

## Regression coverage

`tests/test_context.py` checks that the context exposes no hidden evaluator methods and that all agents and monitors run through the visible-only context. `tests/test_agents.py` also checks that the retry baseline no longer bypasses a fault by calling a clean `tool_response()` after the shifted observation is received.

## Fault-label redaction

Fault injectors may store evaluator provenance in `observation.metadata["faults"]` so reports can explain what happened after evaluation. `redact_response_for_policy()` removes those labels before agent or monitor decisions. Tests cover both the redaction function and runner-level policy inputs.
