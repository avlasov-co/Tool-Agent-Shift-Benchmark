"""Recursive defensive freezing for values crossing public trust boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from tool_agent_shift_benchmark.core.serialization import canonicalize

POLICY_DATA_IMMUTABILITY_CONTRACT = "policy-data-immutability-v1"


def _freeze_normalized(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_normalized(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_normalized(item) for item in value)
    return value


def deep_freeze(value: Any, *, path: str = "$") -> Any:
    """Return an alias-free immutable representation of canonical JSON data."""

    return _freeze_normalized(canonicalize(value, path=path))


def freeze_mapping(value: Any, *, path: str = "$") -> Mapping[str, Any]:
    """Freeze a value and require its outer shape to be a mapping."""

    frozen = deep_freeze(value, path=path)
    if not isinstance(frozen, Mapping):
        raise ValueError(f"{path} must be a mapping")
    return frozen


def mutable_copy(value: Any, *, path: str = "$") -> Any:
    """Return a fresh canonical JSON-shaped copy for serialization or mutation."""

    return canonicalize(value, path=path)
