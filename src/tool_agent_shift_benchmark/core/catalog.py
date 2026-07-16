"""Validated plugin catalog with metadata-only lazy entry-point discovery."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any

from tool_agent_shift_benchmark.agents import AGENTS
from tool_agent_shift_benchmark.core.contracts import (
    CONTRACT_VERSION,
    ISOLATED_TRUST_LEVELS,
    PluginDescriptor,
    TrustLevel,
    validate_plugin_factory,
)
from tool_agent_shift_benchmark.core.evaluator import HiddenStateEvaluator
from tool_agent_shift_benchmark.core.isolation import IsolatedPluginFactory, entry_point_import_root
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment
from tool_agent_shift_benchmark.faults import FAULTS
from tool_agent_shift_benchmark.monitors.composite import CompositeMonitor

PLUGIN_DISCOVERY_CONTRACT = "plugin-discovery-v1"
PLUGIN_DESCRIPTOR_METADATA_FIELD = "TASB-Plugin-Descriptor"
PLUGIN_DESCRIPTOR_METADATA_FILE = "tasb_plugin_descriptors.json"

BUILTIN_ENVIRONMENTS = {
    "file_ops": FileOpsEnvironment,
    "calendar_ops": CalendarOpsEnvironment,
    "risk_ops": RiskOpsEnvironment,
}
BUILTIN_MONITORS = {"composite": CompositeMonitor}
BUILTIN_EVALUATORS = {"hidden_state_evaluator": HiddenStateEvaluator}


class PluginDiscoveryError(ValueError):
    """Static entry-point metadata is missing, malformed, or ambiguous."""


class PluginImportError(ImportError):
    """An explicitly selected plugin implementation could not be imported."""


@dataclass(frozen=True)
class LazyPluginRegistration:
    descriptor: PluginDescriptor
    entry_point: Any


def _entry_point_identifier(entry_point: Any) -> str:
    value = str(getattr(entry_point, "value", "")).strip()
    if "[" in value:
        value = value.split("[", 1)[0].strip()
    if not value:
        raise PluginDiscoveryError("entry point is missing its implementation identifier")
    return value


def _metadata_payloads(entry_point: Any) -> tuple[Any, ...]:
    direct = getattr(entry_point, "tasb_plugin_descriptor", None)
    if direct is not None:
        return (direct,)
    distribution = getattr(entry_point, "dist", None)
    metadata = getattr(distribution, "metadata", None)
    if metadata is not None:
        get_all = getattr(metadata, "get_all", None)
        if callable(get_all):
            fields = tuple(get_all(PLUGIN_DESCRIPTOR_METADATA_FIELD) or ())
            if fields:
                return fields
        elif isinstance(metadata, Mapping):
            raw = metadata.get(PLUGIN_DESCRIPTOR_METADATA_FIELD)
            if raw is not None:
                return (raw,)
    read_text = getattr(distribution, "read_text", None)
    text = read_text(PLUGIN_DESCRIPTOR_METADATA_FILE) if callable(read_text) else None
    if text is None:
        return ()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PluginDiscoveryError(f"{PLUGIN_DESCRIPTOR_METADATA_FILE} is not valid JSON: {exc.msg}") from exc
    if isinstance(payload, Mapping):
        return (payload,)
    if isinstance(payload, list):
        return tuple(payload)
    raise PluginDiscoveryError(f"{PLUGIN_DESCRIPTOR_METADATA_FILE} must contain an object or array of objects")


def _mapping_payload(raw: Any) -> Mapping[str, Any]:
    if isinstance(raw, Mapping):
        return raw
    if not isinstance(raw, str):
        raise PluginDiscoveryError("plugin descriptor metadata must be a JSON object")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PluginDiscoveryError(f"plugin descriptor metadata is not valid JSON: {exc.msg}") from exc
    if not isinstance(value, Mapping):
        raise PluginDiscoveryError("plugin descriptor metadata must decode to an object")
    return value


def _entry_point_descriptor(kind: str, entry_point: Any) -> PluginDescriptor:
    name = str(getattr(entry_point, "name", ""))
    payloads = _metadata_payloads(entry_point)
    if not payloads:
        raise PluginDiscoveryError(
            f"missing non-executable {PLUGIN_DESCRIPTOR_METADATA_FIELD} metadata for {kind}:{name}"
        )
    matches: list[PluginDescriptor] = []
    for raw in payloads:
        payload = _mapping_payload(raw)
        if str(payload.get("kind", "")) != kind or str(payload.get("name", "")) != name:
            continue
        try:
            matches.append(PluginDescriptor.from_mapping(payload))
        except ValueError as exc:
            raise PluginDiscoveryError(f"invalid descriptor for plugin {kind}:{name}: {exc}") from exc
    if len(matches) != 1:
        detail = "missing matching" if not matches else "duplicate matching"
        raise PluginDiscoveryError(f"{detail} descriptor metadata for plugin {kind}:{name}")
    descriptor = matches[0]
    identifier = _entry_point_identifier(entry_point)
    if descriptor.implementation_identifier != identifier:
        raise PluginDiscoveryError(
            f"entry-point implementation mismatch for {kind}:{name}: "
            f"descriptor {descriptor.implementation_identifier!r}, entry point {identifier!r}"
        )
    if descriptor.trust_level not in ISOLATED_TRUST_LEVELS:
        raise PluginDiscoveryError(
            f"entry-point plugin {kind}:{name} must declare external_restricted or untrusted_isolated trust"
        )
    return descriptor


class PluginCatalog:
    """Built-ins, explicit registrations, and lazy Python entry points."""

    GROUPS = {
        "agent": "tasb.agents",
        "environment": "tasb.environments",
        "shift": "tasb.shifts",
        "monitor": "tasb.monitors",
        "evaluator": "tasb.evaluators",
        "reporter": "tasb.reporters",
    }

    def __init__(self, include_external: bool = True):
        self._items: dict[str, dict[str, Any]] = {kind: {} for kind in self.GROUPS}
        self._descriptors: dict[tuple[str, str], PluginDescriptor] = {}
        self._pending: dict[tuple[str, str], LazyPluginRegistration] = {}
        self._discovery_errors: dict[tuple[str, str], PluginDiscoveryError] = {}
        self._import_errors: dict[tuple[str, str], PluginImportError] = {}
        self._add_builtins()
        if include_external:
            self._discover_entry_points()

    def _has_identifier(self, key: tuple[str, str]) -> bool:
        return key in self._descriptors or key in self._pending or key in self._discovery_errors

    def _add(self, descriptor: PluginDescriptor, factory: Any) -> None:
        if descriptor.kind not in self._items:
            raise ValueError(f"unsupported plugin kind: {descriptor.kind!r}")
        key = (descriptor.kind, descriptor.name)
        if self._has_identifier(key):
            raise ValueError(f"duplicate {descriptor.kind} plugin identifier: {descriptor.name}")
        if descriptor.trust_level in ISOLATED_TRUST_LEVELS:
            selected_factory = IsolatedPluginFactory(
                descriptor,
                import_root=entry_point_import_root(factory, descriptor.implementation_identifier),
            )
        else:
            validate_plugin_factory(descriptor, factory)
            selected_factory = factory
        self._items[descriptor.kind][descriptor.name] = selected_factory
        self._descriptors[key] = descriptor

    def _add_builtin(self, kind: str, name: str, factory: Any) -> None:
        self._add(
            PluginDescriptor.for_factory(
                kind,
                name,
                factory,
                trust_level=TrustLevel.BUILTIN_TRUSTED,
            ),
            factory,
        )

    def _add_builtins(self) -> None:
        for name, value in AGENTS.items():
            self._add_builtin("agent", name, value)
        for name, value in BUILTIN_ENVIRONMENTS.items():
            self._add_builtin("environment", name, value)
        for name, value in FAULTS.items():
            self._add_builtin("shift", name, value)
        for name, value in BUILTIN_MONITORS.items():
            self._add_builtin("monitor", name, value)
        for name, value in BUILTIN_EVALUATORS.items():
            self._add_builtin("evaluator", name, value)

    def _discover_entry_points(self) -> None:
        discovered = entry_points()
        for kind, group in self.GROUPS.items():
            selected = discovered.select(group=group) if hasattr(discovered, "select") else discovered.get(group, [])
            ordered = sorted(
                selected,
                key=lambda item: (str(getattr(item, "name", "")), str(getattr(item, "value", ""))),
            )
            by_name: dict[str, list[Any]] = {}
            for entry_point in ordered:
                by_name.setdefault(str(getattr(entry_point, "name", "")), []).append(entry_point)
            for name, candidates in sorted(by_name.items()):
                key = (kind, name)
                if len(candidates) != 1 or self._has_identifier(key):
                    self._pending.pop(key, None)
                    self._discovery_errors[key] = PluginDiscoveryError(f"duplicate {kind} plugin identifier: {name}")
                    continue
                try:
                    descriptor = _entry_point_descriptor(kind, candidates[0])
                except PluginDiscoveryError as exc:
                    self._discovery_errors[key] = exc
                    continue
                self._pending[key] = LazyPluginRegistration(descriptor, candidates[0])

    def _raise_discovery_error(self, key: tuple[str, str]) -> None:
        error = self._discovery_errors.get(key)
        if error is not None:
            raise PluginDiscoveryError(str(error)) from error

    def _load_requested(self, kind: str, name: str) -> Any:
        key = (kind, name)
        cached_error = self._import_errors.get(key)
        if cached_error is not None:
            raise PluginImportError(str(cached_error)) from cached_error
        registration = self._pending.get(key)
        if registration is None:
            raise KeyError(f"unknown {kind} plugin: {name}")
        factory = IsolatedPluginFactory(
            registration.descriptor,
            import_root=entry_point_import_root(
                registration.entry_point,
                registration.descriptor.implementation_identifier,
            ),
        )
        self._items[kind][name] = factory
        self._descriptors[key] = registration.descriptor
        del self._pending[key]
        return factory

    def names(self, kind: str) -> list[str]:
        if kind not in self._items:
            raise KeyError(kind)
        return sorted(
            set(self._items[kind])
            | {name for candidate_kind, name in self._pending if candidate_kind == kind}
            | {name for candidate_kind, name in self._discovery_errors if candidate_kind == kind}
        )

    def register(self, descriptor: PluginDescriptor, factory: Any) -> None:
        """Register an explicitly supplied plugin through the v2 validator."""

        self._add(descriptor, factory)

    def get(self, kind: str, name: str) -> Any:
        if kind not in self._items:
            raise KeyError(kind)
        key = (kind, name)
        self._raise_discovery_error(key)
        item = self._items[kind].get(name)
        return item if item is not None else self._load_requested(kind, name)

    def descriptor(self, kind: str, name: str) -> PluginDescriptor:
        if kind not in self._items:
            raise KeyError(kind)
        key = (kind, name)
        self._raise_discovery_error(key)
        descriptor = self._descriptors.get(key)
        if descriptor is not None:
            return descriptor
        registration = self._pending.get(key)
        if registration is None:
            raise KeyError(f"unknown {kind} plugin: {name}")
        return registration.descriptor

    def descriptors(self) -> list[PluginDescriptor]:
        values = dict(self._descriptors)
        values.update({key: registration.descriptor for key, registration in self._pending.items()})
        return [values[key] for key in sorted(values) if key not in self._discovery_errors]

    def discovery_errors(self) -> list[dict[str, str]]:
        return [
            {"kind": kind, "name": name, "error": str(self._discovery_errors[(kind, name)])}
            for kind, name in sorted(self._discovery_errors)
        ]

    def validate(self, selections: dict[str, list[str]] | None = None) -> None:
        if selections is None:
            if self._discovery_errors:
                key = sorted(self._discovery_errors)[0]
                self._raise_discovery_error(key)
            for descriptor in self.descriptors():
                if descriptor.contract_version != CONTRACT_VERSION:
                    raise ValueError(
                        f"incompatible contract version for {descriptor.kind}:{descriptor.name}: "
                        f"{descriptor.contract_version}"
                    )
                factory = self._items[descriptor.kind].get(descriptor.name)
                if factory is not None and not getattr(factory, "_tasb_isolated_factory", False):
                    validate_plugin_factory(descriptor, factory)
            return
        for kind, names in sorted(selections.items()):
            if kind not in self.GROUPS:
                raise KeyError(kind)
            for name in sorted(names):
                descriptor = self.descriptor(kind, name)
                if descriptor.contract_version != CONTRACT_VERSION:
                    raise ValueError(f"incompatible contract version for {kind}:{name}: {descriptor.contract_version}")
                factory = self.get(kind, name)
                if not getattr(factory, "_tasb_isolated_factory", False):
                    validate_plugin_factory(descriptor, factory)

    def as_dict(self) -> list[dict[str, Any]]:
        return [descriptor.to_dict() for descriptor in self.descriptors()]


def default_catalog() -> PluginCatalog:
    return PluginCatalog()
