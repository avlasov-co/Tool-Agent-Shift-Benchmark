"""Strict canonical serialization for scientific and identity-bearing data."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, TypeVar

SERIALIZATION_SCHEMA_VERSION = "1"

_DATACLASS_REGISTRY: set[type[Any]] = set()
_ENUM_REGISTRY: set[type[Enum]] = set()
_T = TypeVar("_T", bound=type[Any])


class CanonicalSerializationError(TypeError):
    """An unsupported value was found at an exact canonical field path."""

    def __init__(self, path: str, value: Any, reason: str):
        self.path = path
        self.value_type = type(value).__name__
        self.reason = reason
        super().__init__(f"{reason} at {path} (type={self.value_type})")


def register_dataclass(cls: _T) -> _T:
    if not is_dataclass(cls):
        raise TypeError(f"cannot register non-dataclass {cls!r}")
    _DATACLASS_REGISTRY.add(cls)
    return cls


def register_enum(cls: _T) -> _T:
    if not isinstance(cls, type) or not issubclass(cls, Enum):
        raise TypeError(f"cannot register non-enum {cls!r}")
    _ENUM_REGISTRY.add(cls)
    return cls


def _field_path(path: str, name: str) -> str:
    if name.isidentifier():
        return f"{path}.{name}"
    escaped = json.dumps(name, ensure_ascii=False)
    return f"{path}[{escaped}]"


def canonicalize(value: Any, *, path: str = "$") -> Any:
    """Validate and normalize a supported value into JSON primitives.

    Floats must be finite IEEE-754 binary64 values. Encoding uses Python's
    shortest round-trip representation, preserves ``-0.0``, and performs no
    decimal rounding or string conversion.
    """

    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalSerializationError(path, value, "non-finite floats are not supported")
        return value
    if isinstance(value, Enum):
        if type(value) not in _ENUM_REGISTRY:
            raise CanonicalSerializationError(path, value, "enum type is not registered")
        return canonicalize(value.value, path=path)
    if is_dataclass(value) and not isinstance(value, type):
        if type(value) not in _DATACLASS_REGISTRY:
            raise CanonicalSerializationError(path, value, "dataclass type is not registered")
        return {
            field.name: canonicalize(getattr(value, field.name), path=_field_path(path, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        keys = list(value.keys())
        for key in keys:
            if not isinstance(key, str):
                raise CanonicalSerializationError(path, key, "mapping keys must be strings")
        return {key: canonicalize(value[key], path=_field_path(path, key)) for key in sorted(keys)}
    if isinstance(value, (list, tuple)):
        return [canonicalize(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    raise CanonicalSerializationError(path, value, "unsupported canonical value")


def canonical_dumps(value: Any, *, pretty: bool = False) -> str:
    normalized = canonicalize(value)
    options: dict[str, Any] = {
        "allow_nan": False,
        "ensure_ascii": False,
        "sort_keys": True,
    }
    if pretty:
        options["indent"] = 2
    else:
        options["separators"] = (",", ":")
    return str(json.dumps(normalized, **options))


def canonical_bytes(value: Any) -> bytes:
    return canonical_dumps(value).encode("utf-8")


def stable_hash(value: Any, prefix: str = "id") -> str:
    digest = hashlib.sha256(canonical_bytes(value)).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _reject_json_constant(value: str) -> None:
    raise CanonicalSerializationError("$", value, "non-finite JSON constants are not supported")


def canonical_loads(text: str) -> Any:
    value = json.loads(text, parse_constant=_reject_json_constant)
    return canonicalize(value)


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((canonical_dumps(data, pretty=True) + "\n").encode("utf-8"))


def read_json(path: str | Path) -> Any:
    return canonical_loads(Path(path).read_text(encoding="utf-8"))


def write_jsonl(path: str | Path, rows: Iterable[Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes("".join(canonical_dumps(row) + "\n" for row in rows).encode("utf-8"))


def _csv_value(value: Any, *, path: str) -> Any:
    normalized = canonicalize(value, path=path)
    if normalized is None:
        return ""
    if isinstance(normalized, (dict, list)):
        return canonical_dumps(normalized)
    return normalized


def write_csv(
    path: str | Path,
    rows: Iterable[Dict[str, Any]],
    fieldnames: List[str] | None = None,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    materialized = list(rows)
    if fieldnames is None:
        keys: list[str] = []
        for row in materialized:
            for key in row:
                if not isinstance(key, str):
                    raise CanonicalSerializationError("$", key, "CSV field names must be strings")
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row_index, row in enumerate(materialized):
            writer.writerow(
                {key: _csv_value(row.get(key), path=f"$[{row_index}]{_field_path('', key)}") for key in fieldnames}
            )


def read_csv(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))
