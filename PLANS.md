# Major execution plans

Every material repository change starts with a plan in `docs/development/`.
Keep it concise, evidence-based, and update it when assumptions change. Each
plan must include these sections:

1. **Problem statement** — the user-visible problem and desired outcome.
2. **Observed behavior** — commands, inputs, and current evidence; distinguish
   observed facts from hypotheses.
3. **Invariants** — safety, compatibility, determinism, state-boundary, and
   non-destructive requirements that cannot regress.
4. **Affected modules** — source, tests, configurations, scripts, docs, and
   generated artifacts in scope.
5. **Migration strategy** — ordered implementation and data/config transition
   steps, including how existing users or artifacts remain usable.
6. **Compatibility** — Python/package/CLI/config/plugin compatibility and any
   intentional behavior changes.
7. **Tests** — focused tests, full-suite checks, and validation evidence needed
   for the change.
8. **Rollout** — checkpoints, feature exposure, CI/release checks, and the
   expected operational sequence.
9. **Rollback** — reversible commits, preserved data/artifacts, and safe
   recovery actions.
10. **Unresolved risks** — open questions, known failures, assumptions, and
    exact handoff items.

Plans must not assume that generated benchmark output is disposable or that a
green check validates an unsupported experimental claim. Use separate source and
evidence paths, and name any required external decision explicitly.
