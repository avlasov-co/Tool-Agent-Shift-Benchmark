"""Access packaged benchmark resources without depending on a checkout."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

PACKAGE_NAME = "tool_agent_shift_benchmark"
_RESOURCE_ROOT = files(PACKAGE_NAME).joinpath("resources")


class BuiltinResourceError(ValueError):
    """Raised when a requested built-in resource is absent or malformed."""


def _resource(category: str, name: str):
    if not name or Path(name).name != name:
        raise BuiltinResourceError(f"invalid built-in {category} resource name: {name!r}")
    target = _RESOURCE_ROOT.joinpath(category, name)
    if not target.is_file():
        raise BuiltinResourceError(f"packaged {category} resource is missing: {name}")
    return target


def read_builtin_resource(category: str, name: str) -> bytes:
    """Return packaged resource bytes, including from a zipped installation."""

    return _resource(category, name).read_bytes()


def builtin_config_names() -> tuple[str, ...]:
    configs = _RESOURCE_ROOT.joinpath("configs")
    return tuple(sorted(item.name.removesuffix(".yaml") for item in configs.iterdir() if item.name.endswith(".yaml")))


def builtin_suite_names() -> tuple[str, ...]:
    """Return the stable names of packaged, versioned suite manifests."""

    suites = _RESOURCE_ROOT.joinpath("suites")
    return tuple(sorted(item.name.removesuffix(".json") for item in suites.iterdir() if item.name.endswith(".json")))


def read_builtin_suite(name: str) -> dict[str, object]:
    """Load a packaged suite manifest by its exact public name."""

    candidate = name.removeprefix("builtin:").removesuffix(".json")
    if candidate not in builtin_suite_names():
        choices = ", ".join(builtin_suite_names())
        raise BuiltinResourceError(f"unknown built-in suite {name!r}; choose one of: {choices}")
    value = json.loads(read_builtin_resource("suites", f"{candidate}.json"))
    if not isinstance(value, dict):
        raise BuiltinResourceError(f"packaged suite manifest must be an object: {candidate}")
    return value


def _normalise_config_name(value: str) -> str | None:
    candidate = value.removeprefix("builtin:")
    if candidate.endswith(".yaml"):
        candidate = candidate.removesuffix(".yaml")
    if candidate in builtin_config_names() and (
        value.startswith("builtin:") or Path(value).parent == Path(".") or value == f"configs/{candidate}.yaml"
    ):
        return candidate
    return None


def read_builtin_config(name: str) -> tuple[str, str]:
    """Return ``(display_name, YAML text)`` for a supported named config."""

    normalised = _normalise_config_name(name)
    if normalised is None:
        choices = ", ".join(builtin_config_names())
        raise BuiltinResourceError(f"unknown built-in configuration {name!r}; choose one of: {choices}")
    resource_name = f"{normalised}.yaml"
    return f"builtin:{normalised}", read_builtin_resource("configs", resource_name).decode("utf-8")


def load_config_text(path_or_name: str | Path) -> tuple[str, str]:
    """Load an explicit external path or a named package configuration."""

    candidate = Path(path_or_name)
    if candidate.is_file():
        return str(candidate), candidate.read_text(encoding="utf-8")
    if isinstance(path_or_name, str):
        try:
            return read_builtin_config(path_or_name)
        except BuiltinResourceError:
            pass
    choices = ", ".join(builtin_config_names())
    raise FileNotFoundError(
        f"configuration {str(path_or_name)!r} was not found; pass an external file path or a built-in name: {choices}"
    )
