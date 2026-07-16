# Plugin threat model

## Scope and protected assets

This model covers built-in, programmatically registered, and Python
entry-point plugins used as environments, agents, shifts, monitors, evaluators,
and reporters. Protected assets are hidden evaluator state and ground truth,
authoritative scenario/split identity, policy credentials and host environment
variables, unrelated user files, runner availability, deterministic experiment
identity, canonical artifacts, and complete failure denominators.

## Trust tiers

| Tier | Intended source | Execution expectation |
| --- | --- | --- |
| `builtin_trusted` | code shipped in this distribution | validated, in-process |
| `local_trusted` | explicitly registered reviewed local code | validated, in-process |
| `external_restricted` | installed third-party package | validated, bounded subprocess |
| `untrusted_isolated` | adversarial or unknown implementation | validated, stricter bounded subprocess |

Trust is declared in the validated plugin descriptor and recorded with the
implementation identifier, configuration hash, capabilities, and actual
isolation mode. A tier never silently downgrades to in-process execution.

## Threat actors and attack paths

- A policy plugin may inspect arguments, nested aliases, closures, globals, or
  shared mutable state to recover hidden state or influence later plugins.
- A shift may use the historical environment argument to call
  `hidden_ground_truth`, inspect private fields, mutate lifecycle state, access
  filesystem/network handles, or read authoritative scenario metadata.
- An installed entry point may execute code merely because a user lists plugin
  names or validates an unrelated configuration.
- A registration caller may supply a valid-looking descriptor and a factory
  with missing methods, a different runtime identity, malformed configuration
  schema, duplicate name, or unsupported contract.
- Restricted code may hang, crash, allocate resources, emit unbounded output,
  corrupt the RPC stream, probe inherited credentials, access unrelated files,
  or open network connections.
- Failure handling may drop crashed episodes, accidentally improve reported
  rates, or misclassify infrastructure failures as safe/unsafe outcomes.

## Security controls

- Contract v2 enumerates the complete orchestrator-used interface per kind and
  validates identity, lifecycle, configuration schema/hash, capabilities,
  serialization, trust, and implementation identity at every registration
  path.
- Policy adapters and `ShiftContext` are capability-minimal values built from
  defensive immutable copies. They do not contain the environment, evaluator,
  filesystem, network, or credential handles.
- Policy-visible records use recursive immutable mappings/tuples. Canonical
  serialization thaws only into fresh JSON-shaped values.
- Entry-point discovery reads metadata without importing implementations.
  Import and instantiation happen only for an explicitly requested plugin.
- Restricted/untrusted execution uses a structured bounded subprocess protocol
  with a sanitized environment, controlled temporary cwd, startup and per-call
  timeouts, output limits, deterministic termination, and supported resource
  limits. Protocol, crash, and limit failures become structured orchestration
  failures.
- Checkpoints, manifests, and analysis retain failed planned episodes and record
  descriptor/version/implementation/isolation information.

## Trust boundaries

1. Configuration and entry-point metadata cross into descriptor validation;
   they are data, never imported code.
2. Environment output crosses into the policy boundary only after evaluator
   labels/provenance are removed and values are defensively frozen.
3. Shift code receives `ShiftContext`, not the environment. Only declared
   public scenario, schema, timing, schedule, channel, and deterministic RNG
   information crosses.
4. Policy decisions cross back through typed response validation before
   oversight or execution.
5. Hidden environment state crosses only to the trusted evaluator boundary and
   evaluator-only artifacts.
6. Restricted/untrusted calls cross an explicit JSON RPC/process boundary; the
   child receives no arbitrary parent environment or working directory.

## Out of scope and honest limitations

The subprocess boundary is defense in depth, not a general-purpose secure
container. On platforms without kernel-enforced namespaces, seccomp/sandbox
profiles, or equivalent controls, Python-level network denial and resource
limits cannot contain hostile native extensions, direct syscalls, child-process
escape, all filesystem reads, or kernel vulnerabilities. Package installation
and publisher authenticity are supply-chain concerns outside runtime contract
validation. Plugins granted `builtin_trusted` or `local_trusted` can exercise
ordinary process authority and must be reviewed accordingly.

## Required adversarial evidence

Tests must cover hidden-attribute inspection, nested/list/alias/shared-state
mutation, eager-import traps, duplicate/invalid registrations, infinite loops,
oversized output, crashes, malformed RPC output, filesystem probing,
environment-variable probing, deterministic termination, and denominator
retention. The final review must inspect registration bypasses, credential
inheritance, mutable aliases, eager execution, hidden-state exposure, sandbox
claims, and analysis failure handling.
