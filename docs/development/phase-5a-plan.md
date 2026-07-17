# Phase 5A public plugin contract and trust-boundary plan

## Problem statement

Plugin contract v1 describes only a small part of the runtime surface. The
catalog eagerly imports every installed entry point, environment-specific
policy behavior is dispatched centrally by name, shifts receive the complete
environment object, and several policy-visible frozen dataclasses retain
mutable nested containers. External code also executes in the runner process
without a declared trust model or bounded failure containment. Phase 5A must
replace those conventions with a versioned, capability-minimal, validated
public contract and honest isolation boundary.

## Observed behavior

- The clean Phase 4B terminal commit is `a59629f`; its baseline suite passes all
  501 tests after byte compilation.
- `PluginCatalog` imports all entry points during construction, accepts
  descriptor overrides after weaker registration, and checks only one method
  per plugin kind.
- Contract-v1 descriptors omit implementation identity, configuration schema
  and hash, trust level, and isolation mode.
- `ObservationContext` branches on the three built-in environment names and is
  constructed by introspecting the environment object.
- `ShiftPlugin.apply` receives the complete environment and can inspect hidden
  evaluator state or mutable internal state.
- `Observation`, `ToolResponse`, actions, decisions, monitor decisions, memory
  records, and contexts contain nested dictionaries or lists despite frozen
  top-level dataclasses.
- Plugin crashes become orchestration errors, but in-process hangs, excessive
  output, environment inheritance, and process crashes are unbounded.

## Invariants

- Policy and shift plugins receive only documented public capabilities; hidden
  evaluator state, authoritative split/scenario identity, and mutable
  environment internals never cross those boundaries.
- Every registration path uses the same descriptor, schema, capability, and
  interface validation.
- Metadata discovery does not import or instantiate entry-point code; only an
  explicitly selected plugin may be loaded.
- Policy-visible values are recursively immutable defensive copies and remain
  canonically serializable with stable scientific hashes.
- Built-in, local, restricted, and isolated trust levels are explicit and
  recorded with implementation identity and isolation mode.
- Restricted/untrusted execution is bounded. Crashes, timeouts, oversized or
  malformed output, and protocol violations are structured orchestration
  failures that remain represented in checkpoints/manifests and denominators.
- Isolation documentation distinguishes process containment and best-effort
  controls from an operating-system security sandbox.
- Phase 4B compatibility readers and historical evidence remain untouched.

## Affected modules

- Public contracts and registration: `core/contracts.py`, `core/catalog.py`,
  `core/plugin_catalog.py`, configuration parsing, identity, CLI, artifacts,
  and run manifests.
- Policy/environment boundary: `core/context.py`, environment base and
  first-party environments, agents, monitors, and orchestration.
- Shift boundary: faults, fault composition, schedules, and orchestration.
- Immutability and serialization: core policy records, memory, action records,
  traces, schemas, and defensive boundary constructors.
- Isolation: a structured subprocess protocol, worker, proxies, resource
  limits, sanitized launch configuration, failure records, and fixtures.
- Documentation/tests: plugin v1 migration notes, threat model, contract,
  synthetic environment, malicious boundary, discovery, and isolation tests.

## Migration strategy

1. Introduce plugin contract v2, typed descriptor/configuration schema and
   trust data, exhaustive per-kind interface validation, and consistent
   registration. Advance scientific identity for the changed descriptor.
2. Move recommendation, visible extraction/validation, abstention, and action
   schema behavior behind environment-provided policy adapters. Remove central
   environment-name dispatch and prove a synthetic plugin environment works.
3. Replace the environment argument to shifts with a versioned immutable
   `ShiftContext` containing only declared public/schedule/timing data and a
   deterministic local RNG capability.
4. Add one recursive freeze/thaw boundary and apply it to all policy-visible
   observations, contexts, schemas, decisions, monitor inputs, and memory.
5. Store entry-point metadata as lazy registrations, resolve imports only from
   explicit `get`/selected validation, and deterministically reject duplicates
   and incompatible descriptors without touching unrelated plugins.
6. Route restricted and untrusted callable plugins through a bounded subprocess
   RPC protocol with sanitized environment/cwd, time/output/resource limits,
   deterministic termination, and structured failure conversion.

## Compatibility

- New runtime registrations require contract version `2`. Contract-v1
  descriptors receive a clear migration error; no implicit v1 behavior is
  relabeled as v2.
- Historical episode/config/manifest readers remain supported. New identities
  bind the v2 descriptors and isolation data rather than rewriting old records.
- Built-in names and ordinary CLI surfaces remain stable. Entry-point packages
  must publish non-executable descriptor metadata and an importable
  implementation identifier.
- Python 3.10–3.14 remains supported. Resource-limit enforcement is conditional
  on platform support and is recorded accurately.

## Tests

- Checkpoint 36: first-party/test conformance and failures for missing methods,
  descriptor/schema/version errors, implementation mismatch, and duplicates.
- Checkpoint 37: every first-party adapter plus a new synthetic environment
  without central runner changes or name dispatch.
- Checkpoint 38: malicious shifts cannot obtain hidden attributes, state, or
  unrestricted handles; context schema and deterministic RNG are verified.
- Checkpoint 39: nested, list, alias, and shared-state mutation attempts by
  agents and monitors fail and cannot affect later calls or episodes.
- Checkpoint 40: raising entry points remain unloaded during list/name/metadata
  validation; selecting one produces a useful import/contract error while
  unrelated commands work.
- Checkpoint 41: infinite loop, excessive output, process crash, malformed
  response, filesystem probing, and environment probing fixtures produce
  bounded structured failures and remain in denominators.
- Every checkpoint runs focused tests, compilation, Ruff, format-check, strict
  mypy, full tests/coverage as appropriate, and `git diff --check` before its
  separate commit. Terminal validation adds audit, distribution/release smoke,
  package build/install, artifact verification, and focused security review.

## Rollout

- Work on `codex/phase-5a-plugin-security` from `a59629f`.
- Commit Checkpoints 36–41 separately in order. Keep planning and final
  validation documentation as distinct commits.
- Update `phase-5a-progress.md` with exact contracts, commands, results, and
  unresolved limitations at every checkpoint.
- Generate only temporary or named run-scoped engineering evidence; never
  rewrite historical root results merely to satisfy validation.

## Rollback

Each numbered checkpoint is a coherent revert boundary. Reverting a checkpoint
must not delete user artifacts, clean the checkout, restore generated evidence,
or relabel historical records. Compatibility failures are fixed forward inside
the current checkpoint; a contract-v1 restoration requires an explicit new
migration plan rather than bypassing v2 validation.

## Unresolved risks

- Python subprocess isolation is not equivalent to a kernel sandbox. Socket
  blocking, resource limits, cwd control, and environment sanitization reduce
  exposure but cannot defeat native code or all platform-specific escape paths.
- Stateful restricted environments require a carefully bounded public adapter
  and RPC lifecycle; unsupported combinations must fail closed, not fall back
  to in-process execution.
- Plugin metadata sidecars must be authenticated by package provenance outside
  this repository; contract validation proves shape/compatibility, not publisher
  identity.
- Failed episodes must remain countable without fabricating safety outcomes;
  analysis changes must preserve the distinction between orchestration failure
  and unsafe execution.
