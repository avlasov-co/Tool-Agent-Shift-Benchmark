# Plugin contract v1 to v2 migration

Contract v2 is a deliberate compatibility boundary. Runtime registration no
longer accepts a v1 descriptor or infers undocumented behavior from a single
method. Historical records remain readable, but new runs and plugins use
contract version `2`.

## Descriptor migration

Replace the v1 fields `kind`, `name`, `version`, `contract_version`, optional
`capabilities`, and free-form `metadata` with a complete
`plugin-descriptor-v2` record:

- `schema_version: plugin-descriptor-v2`;
- `kind`, `name`, and implementation `version`;
- `contract_version: "2"`;
- stable `implementation_identifier` in `module:qualname` form;
- a `plugin-configuration-schema-v1` object and its canonical
  `plugin_config_*` hash;
- one trust level: `builtin_trusted`, `local_trusted`,
  `external_restricted`, or `untrusted_isolated`;
- declared capabilities and the actual isolation mode.

Programmatic registrations should construct the descriptor with
`PluginDescriptor.for_factory(...)`; this derives the implementation identity,
canonical configuration hash, version, and declared capabilities before the
same validator used by built-ins and entry points runs.

## Required interfaces

- Environments implement reset, scenario generation/replay metadata, tool
  response and execution, lifecycle/clock operations, visible constraints,
  pure counterfactual scoring support, and evaluator-only state access.
- Agents implement `decide`.
- Shifts implement `apply(response, context)` and `channel_descriptor`.
  `context` is immutable `shift-context-v1`; call `context.rng()` for a fresh
  deterministic component-local stream. Environment objects and separate RNG
  parameters are no longer accepted.
- Monitors implement `check`.
- Evaluators implement `score_action`, `score_intervention`, and `score`.
- Reporters implement `report`.

Factories must have a stable declared name and be non-abstract. Descriptor
identity, configuration schema/hash, and capability declarations must match the
implementation. Duplicate names and partial implementations fail registration.

## Immutable policy data

Contract-v2 policy code must treat all inputs as immutable. Observation data,
constraints, metadata, action parameters, adapter schemas/candidates, and
memory values implement read-only `Mapping` interfaces; JSON arrays are
tuples. Do not require concrete `dict`/`list` types or mutate input aliases.
Create an explicit local copy with canonical serialization when mutable
scratch data is needed. Returned actions and decisions are defensively copied
and recursively frozen by their typed constructors.

## Entry-point migration

Entry-point packages must publish non-executable v2 descriptor metadata and an
importable implementation identifier. Publish one canonical descriptor JSON
object in a `TASB-Plugin-Descriptor` core-metadata field, or package a
`tasb_plugin_descriptors.json` object/array in distribution metadata. The
descriptor `kind` and `name` must match the entry-point group/name, and its
`implementation_identifier` must exactly match the entry-point value.

`plugin-discovery-v1` lists and validates this static data without importing
the implementation. Import occurs only when configuration explicitly selects
the plugin. Installed entry-point plugins must declare `external_restricted`
or `untrusted_isolated`; reviewed `local_trusted` code uses explicit
programmatic registration. Contract-v1 packages receive a scoped
incompatible-contract error and must be upgraded or explicitly adapted in
their own package; the benchmark does not relabel v1 behavior as v2.

## Trust migration

Use `local_trusted` only for reviewed code the caller explicitly chooses to run
with ordinary process authority. Installed third-party packages should use
`external_restricted`; unknown/adversarial code should use
`untrusted_isolated`. Restricted and untrusted descriptors cannot declare
`in_process` execution. Isolation is bounded process containment and is not a
general kernel sandbox; see `docs/security/plugin-threat-model.md`.
