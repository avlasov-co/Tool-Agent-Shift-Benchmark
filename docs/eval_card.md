# Evaluation Card

## What the benchmark measures

Safety and usefulness of tool-using agent policies under synthetic tool, observation, memory, and constraint shift.

## What it does not measure

It does not measure real production safety, real trading performance, real calendar reliability, exploit capability, or private-data handling.

## Intended use

Research comparisons of agent policies, monitors, and fault mitigations.

## Non-goals

No real APIs, no operational side effects, no dangerous procedures, no financial advice.

## Safety boundary

All data and environments are synthetic. Faults never mutate hidden ground truth. Agents and monitors receive a visible-only `ObservationContext`; hidden ground truth and evaluator execution methods are used only after the policy decision for scoring and replay.

## Known limitations

Simple policies, compact environments, and synthetic assumptions limit external validity.

## Reproducibility notes

Use deterministic seeds. Run `bash scripts/run_repro.sh`.


## Evaluator leakage controls

Agents and monitors should not be able to access hidden evaluator state. The current implementation enforces this by passing `ObservationContext` instead of the full environment object, by redacting evaluator-only fault labels before policy decisions, and by testing that hidden methods such as `hidden_ground_truth`, `tool_response`, and `execute` are absent from that context.
