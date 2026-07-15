from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any

from src.agents import AGENTS
from src.core.contracts import CONTRACT_VERSION, PluginDescriptor
from src.environments.calendar_ops import CalendarOpsEnvironment
from src.environments.file_ops import FileOpsEnvironment
from src.environments.risk_ops import RiskOpsEnvironment
from src.faults import FAULTS
from src.monitors.composite import CompositeMonitor

BUILTIN_ENVIRONMENTS = {
    "file_ops": FileOpsEnvironment,
    "calendar_ops": CalendarOpsEnvironment,
    "risk_ops": RiskOpsEnvironment,
}
BUILTIN_MONITORS = {"composite": CompositeMonitor}


class PluginCatalog:
    """Catalog of built-ins plus Python entry-point plugins."""

    GROUPS = {
        "agent": "tasb.agents",
        "environment": "tasb.environments",
        "shift": "tasb.shifts",
        "monitor": "tasb.monitors",
        "reporter": "tasb.reporters",
    }

    def __init__(self, include_external: bool = True):
        self._items: dict[str, dict[str, Any]] = {k: {} for k in self.GROUPS}
        self._descriptors: dict[tuple[str, str], PluginDescriptor] = {}
        self._add_builtins()
        if include_external:
            self._load_entry_points()

    def _add(self, kind: str, name: str, factory: Any, version: str = "builtin") -> None:
        if name in self._items[kind]:
            raise ValueError(f"duplicate {kind} plugin identifier: {name}")
        descriptor = PluginDescriptor(kind, name, version=version)
        if descriptor.contract_version != CONTRACT_VERSION:
            raise ValueError(f"incompatible contract version for {kind}:{name}")
        self._items[kind][name] = factory
        self._descriptors[(kind, name)] = descriptor

    def _add_builtins(self) -> None:
        for name, value in AGENTS.items():
            self._add("agent", name, value)
        for name, value in BUILTIN_ENVIRONMENTS.items():
            self._add("environment", name, value)
        for name, value in FAULTS.items():
            self._add("shift", name, value)
        for name, value in BUILTIN_MONITORS.items():
            self._add("monitor", name, value)

    def _load_entry_points(self) -> None:
        groups = self.GROUPS
        eps = entry_points()
        for kind, group in groups.items():
            selected = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
            for ep in selected:
                loaded = ep.load()
                descriptor = getattr(loaded, "descriptor", None) or getattr(loaded, "plugin_descriptor", None)
                if descriptor is None:
                    raise ValueError(f"missing plugin metadata for {kind}:{ep.name}")
                if isinstance(descriptor, dict):
                    descriptor = PluginDescriptor(**descriptor)
                if (
                    not isinstance(descriptor, PluginDescriptor)
                    or descriptor.kind != kind
                    or descriptor.name != ep.name
                ):
                    raise ValueError(f"invalid metadata for plugin {kind}:{ep.name}")
                if descriptor.contract_version != CONTRACT_VERSION:
                    raise ValueError(
                        f"incompatible contract version for {kind}:{ep.name}: {descriptor.contract_version}"
                    )
                self._add(kind, ep.name, loaded, descriptor.version)
                self._descriptors[(kind, ep.name)] = descriptor

    def names(self, kind: str) -> list[str]:
        if kind not in self._items:
            raise KeyError(kind)
        return sorted(self._items[kind])

    def register(self, descriptor: PluginDescriptor, factory: Any) -> None:
        """Register an explicitly supplied plugin (useful for tests and embedding)."""
        self._add(descriptor.kind, descriptor.name, factory, descriptor.version)
        self._descriptors[(descriptor.kind, descriptor.name)] = descriptor

    def get(self, kind: str, name: str) -> Any:
        try:
            return self._items[kind][name]
        except KeyError as exc:
            raise KeyError(f"unknown {kind} plugin: {name}") from exc

    def descriptor(self, kind: str, name: str) -> PluginDescriptor:
        return self._descriptors[(kind, name)]

    def descriptors(self) -> list[PluginDescriptor]:
        return [self._descriptors[key] for key in sorted(self._descriptors)]

    def validate(self, selections: dict[str, list[str]] | None = None) -> None:
        required = {
            "agent": "decide",
            "environment": "tool_response",
            "shift": "apply",
            "monitor": "check",
            "reporter": "report",
        }
        target = selections or {kind: self.names(kind) for kind in self.GROUPS}
        for kind, names in target.items():
            for name in names:
                factory = self.get(kind, name)
                method = required[kind]
                if kind == "reporter" and callable(factory):
                    continue
                if hasattr(factory, method):
                    continue
                if callable(factory):
                    try:
                        instance = factory()
                    except Exception as exc:
                        raise ValueError(f"invalid {kind} plugin {name}: cannot instantiate contract") from exc
                    if hasattr(instance, method):
                        continue
                raise ValueError(f"invalid {kind} plugin {name}: missing {method} contract method")

    def as_dict(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self.descriptors()]


def default_catalog() -> PluginCatalog:
    return PluginCatalog()
