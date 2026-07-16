"""Strict YAML loading and deterministic configuration output."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tool_agent_shift_benchmark.core.serialization import canonicalize


class ConfigSyntaxError(ValueError):
    def __init__(self, path: str | Path, line: int, column: int, problem: str):
        self.path = str(path)
        self.line = line
        self.column = column
        self.problem = problem
        super().__init__(f"{self.path}:{line}:{column}: invalid YAML: {problem}")


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False) -> Any:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            mark = key_node.start_mark
            raise ConfigSyntaxError(
                "<yaml>", mark.line + 1, mark.column + 1, "mapping keys must be scalar and hashable"
            ) from exc
        if duplicate:
            mark = key_node.start_mark
            raise ConfigSyntaxError("<yaml>", mark.line + 1, mark.column + 1, f"duplicate key {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_raw_config(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    try:
        data = yaml.load(text, Loader=_UniqueKeySafeLoader)
    except ConfigSyntaxError as exc:
        raise ConfigSyntaxError(source, exc.line, exc.column, exc.problem) from exc
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        line = mark.line + 1 if mark is not None else 1
        column = mark.column + 1 if mark is not None else 1
        problem = exc.problem or exc.context or type(exc).__name__
        raise ConfigSyntaxError(source, line, column, problem) from exc
    if not isinstance(data, dict):
        raise ConfigSyntaxError(source, 1, 1, "configuration root must be a mapping")
    return data


def dump_config_yaml(data: dict[str, Any]) -> str:
    normalized = canonicalize(data)
    if not isinstance(normalized, dict):
        raise TypeError("configuration output must be a string-keyed mapping")
    return str(
        yaml.safe_dump(
            normalized,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=True,
        )
    )


def write_config_yaml(path: str | Path, data: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump_config_yaml(data), encoding="utf-8")
    return target


def load_config(path: str | Path) -> dict[str, Any]:
    """Load and normalize a strict schema-v2 configuration."""

    from tool_agent_shift_benchmark.core.config_schema import parse_config_data

    return parse_config_data(load_raw_config(path), source=str(path)).to_dict()
