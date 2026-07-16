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
| `external_restricted` | installed third-party package | validated, mandatory bounded subprocess |
| `untrusted_isolated` | adversarial or unknown implementation | validated, mandatory bounded subprocess; no added provenance trust |

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
- `plugin-discovery-v1` reads static descriptor fields or the packaged
  `tasb_plugin_descriptors.json` file without importing implementations.
  Import and instantiation happen inside the child only when an explicitly
  requested factory is actually instantiated; malformed entries remain scoped
  errors and do not disable unrelated names.
- Restricted/untrusted execution uses a structured bounded subprocess protocol
  (`plugin-rpc-v1`) with typed JSON values rather than pickle. It uses an
  allowlisted environment, private temporary cwd, startup and per-call
  timeouts, parent- and child-side output limits, process-group termination on
  POSIX, and available `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_FSIZE`,
  `RLIMIT_NOFILE`, and `RLIMIT_NPROC` controls. The startup result records
  applied and unavailable limits rather than assuming support.
- The child installs a Python audit-hook filesystem/network/process policy.
  Read access is limited to the Python runtime/environment, benchmark package,
  configured plugin import root, and private workspace; writes are limited to
  the workspace. An import root can be a shared site-packages directory, so
  other installed packages may be readable. Socket construction and
  process-spawn audit events are denied.
  Normal Python stdout/stderr is captured and bounded; raw writes that corrupt
  stdout fail strict protocol parsing.
- Agents and monitors can invoke only five parent-side callbacks on the exact
  `ObservationContext` supplied for that call. No arbitrary parent object,
  environment, evaluator, or callable is serialized. Environment policy
  adapters returned by isolated environments remain opaque remote handles with
  only their public adapter methods.
- Plugin startup/call timeouts, output overflow, hard exits, malformed JSON,
  message-identity mismatches, invalid typed values, and remote exceptions are
  distinct structured orchestration failures. The process is terminated after
  terminal transport failures.
- Checkpoints, manifests, and analysis retain failed planned episodes and record
  descriptor/version/implementation/isolation information. Summary rows record
  planned, completed, and infrastructure-failed counts plus
  `unsafe_or_failed_rate` and `safe_completion_rate`; failures are not silently
  removed or fabricated as unsafe actions.

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
container. It does not create a container, VM, mount namespace, seccomp policy,
macOS sandbox profile, Windows AppContainer, or OS firewall rule. The audit hook
and monkeypatches govern ordinary Python operations; hostile native extensions,
FFI, direct syscalls, memory-safety bugs, inherited runtime file descriptors,
and kernel vulnerabilities may bypass them. The Python environment, import
roots, and dependencies remain readable so Python imports work; the boundary
does not promise that only one distribution's files are visible. A plugin may
consume resources below configured limits, and `RLIMIT_AS` behavior differs by
OS.

On POSIX, the parent starts a new session and terminates the process group; on
platforms without `killpg`, it can terminate only the direct worker. Unsupported
resource limits are reported in the isolation manifest. Network denial is
best-effort Python enforcement, not kernel egress isolation. The two isolated
trust labels currently use the same execution mechanism and configurable bound
ranges; `untrusted_isolated` is a provenance/risk declaration, not a claim of a
stronger kernel boundary.

The typed wire contract covers current environment, agent, shift, and monitor
runtime values. An isolated evaluator that requires a live environment object,
and reporters requiring undeclared record types, fail closed with a protocol
violation; they do not fall back to in-process execution. Phase 5B should add a
capability-specific evaluator/reporting protocol rather than serializing live
objects. Package installation, wheel integrity, dependency review, publisher
authenticity, and static metadata signing remain supply-chain concerns outside
runtime descriptor validation. `builtin_trusted` and `local_trusted` plugins
retain ordinary process authority and must be reviewed.

## Required adversarial evidence

Tests must cover hidden-attribute inspection, nested/list/alias/shared-state
mutation, eager-import traps, duplicate/invalid registrations, infinite loops,
oversized output, crashes, malformed RPC output, filesystem probing,
environment-variable probing, deterministic termination, and denominator
retention. The final review must inspect registration bypasses, credential
inheritance, mutable aliases, eager execution, hidden-state exposure, sandbox
claims, and analysis failure handling.
