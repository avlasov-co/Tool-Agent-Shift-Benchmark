# Phase 5B handoff

## Starting point

Phase 5A ends with plugin contract `2`, `plugin-descriptor-v2`,
`environment-policy-adapter-v1`, `shift-context-v1`,
`policy-data-immutability-v1`, `plugin-discovery-v1`, `plugin-rpc-v1`, and
`plugin-isolation-manifest-v1`. Built-in/reviewed-local code is explicitly
in-process. Restricted and untrusted code cannot select in-process execution;
it is imported, validated, and invoked only inside `bounded_subprocess_v1`.

The boundary contains hangs, crashes, output overflow, and malformed transport,
strips parent environment credentials, uses a private cwd, applies supported
resource limits, and preserves failed planned episodes in analysis. It is a
Python/POSIX defense-in-depth boundary, not a kernel security sandbox.

## Highest-priority work

1. Add an optional OS-enforced backend with an explicit capability manifest:
   Linux namespaces/seccomp/cgroups, macOS sandbox profiles, and a Windows job
   object/AppContainer design where available. Keep the current Python boundary
   as a portable fallback only when policy permits it; never label fallback
   enforcement as kernel isolation.
2. Authenticate plugin provenance. Define signed descriptor/sidecar semantics,
   wheel hash pinning, dependency/SBOM capture, publisher policy, revocation,
   and an installation-time review workflow. Contract validation proves shape
   and identity consistency, not package authorship or safety.
3. Add capability-specific isolated evaluator and reporter protocols. Do not
   serialize a live environment, evaluator state object, or arbitrary episode
   graph. Define evaluator snapshots/queries and reporter record batches with
   versioned size/count limits. Until then these unsupported combinations must
   continue to fail closed.
4. Build a cross-platform enforcement matrix. Test each resource limit,
   process-tree termination, filesystem boundary, network policy, and native
   extension escape assumption on every supported OS/Python version. Persist
   actual support in run manifests and make minimum required controls
   configurable for high-assurance runs.
5. Measure subprocess cost and add safe reuse only where identity/state reset
   can be proven. Pooling must preserve episode isolation, deterministic seeds,
   output accounting, timeout accounting, and guaranteed teardown. Never share
   an untrusted process across unrelated plugin identities.

## Follow-on security tests

- Native-extension/FFI and direct-syscall probes, child/grandchild escape, file
  descriptor inheritance, symlink/path-race cases, decompression bombs, memory
  pressure below `RLIMIT_AS`, and callback reentrancy/order attacks.
- Protocol fuzzing for duplicate keys, huge integers/depth, Unicode edge cases,
  NaN/infinity, message replay, request-ID confusion, extra/missing fields,
  handle lifetime, and partial-line output.
- Multi-worker stress with simultaneous timeout/crash/cleanup, orphan scanning,
  retry accounting, checkpoint/resume, and all-failed groups in every analysis
  and report surface.
- Supply-chain cases for descriptor/package mismatch, dependency substitution,
  signature expiry/revocation, editable installs, namespace packages, and
  multiple distributions claiming one identifier.

## Compatibility rule

Phase 5B may add stronger isolation modes and wire capabilities, but it must not
silently grant restricted code in-process execution, widen policy-visible data,
reintroduce eager imports, turn immutable values mutable, or erase failed
episodes. Historical identities/manifests remain readable; new semantics get a
new version and an explicit migration path.
