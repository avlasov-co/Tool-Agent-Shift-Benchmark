# Canonical scientific serialization policy

Scientific and identity-bearing records use canonical serialization schema
version `1`, implemented by `src/core/serialization.py`. The same compact UTF-8
bytes are used for hashes in every process and working directory.

## Supported values

- `null`, booleans, integers, finite floating-point values, and strings;
- mappings with string keys;
- ordered lists and tuples;
- dataclass instances registered explicitly with `register_dataclass`;
- enum instances registered explicitly with `register_enum`.

Mappings are emitted with keys sorted lexicographically. Lists and tuples retain
their order. Dataclasses retain declared field order during validation and are
emitted as sorted-key JSON objects. Enums serialize through their validated
value. Strings are encoded directly as UTF-8 rather than ASCII escape sequences.

## Floating-point policy

Floats are finite Python/IEEE-754 binary64 values. JSON uses Python's shortest
round-trip numeric representation, preserves negative zero as `-0.0`, and does
not round, quantize, or convert values to strings. `NaN`, positive infinity, and
negative infinity are rejected before encoding. Writers set `allow_nan=false`.

## Rejected values and errors

Bytes, sets, paths, arbitrary objects, unregistered dataclasses/enums,
non-string mapping keys, non-finite floats, and unsupported nested values are
rejected. `CanonicalSerializationError` records the exact field path, offending
type, and reason; values are never hidden through `str`, `repr`, or a permissive
JSON default.

## Files and compatibility

Canonical JSON files end with one newline. JSON Lines uses one compact canonical
record and newline per row. New traces, checkpoints, manifests, failure records,
normalized configurations, plugin descriptors, identities, and artifact
metadata use these writers. Compatibility readers parse legacy JSON but apply
the same value validation; malformed or non-finite legacy data fails explicitly
instead of being silently ignored.
