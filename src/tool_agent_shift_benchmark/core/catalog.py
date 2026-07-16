from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any, Mapping

from tool_agent_shift_benchmark.agents import AGENTS
from tool_agent_shift_benchmark.core.contracts import (
    CONTRACT_VERSION,
    PluginDescriptor,
    TrustLevel,
    validate_plugin_factory,
)
from tool_agent_shift_benchmark.core.evaluator import HiddenStateEvaluator
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment
from tool_agent_shift_benchmark.faults import FAULTS
from tool_agent_shift_benchmark.monitors.composite import CompositeMonitor

BUILTIN_ENVIRONMENTS = {
    "file_ops": FileOpsEnvironment,
    "calendar_ops": CalendarOpsEnvironment,
    "risk_ops": RiskOpsEnvironment,
}
BUILTIN_MONITORS = {"composite": CompositeMonitor}
BUILTIN_EVALUATORS = {"hidden_state_evaluator": HiddenStateEvaluator}


class PluginCatalog:
    """Validated catalog of built-ins plus Python entry-point plugins."""

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
        self._add_builtins()
        if include_external:
            self._load_entry_points()

    def _add(self, descriptor: PluginDescriptor, factory: Any) -> None:
        if descriptor.kind not in self._items:
            raise ValueError(f"unsupported plugin kind: {descriptor.kind!r}")
        key = (descriptor.kind, descriptor.name)
        if key in self._descriptors:
            raise ValueError(f"duplicate {descriptor.kind} plugin identifier: {descriptor.name}")
        validate_plugin_factory(descriptor, factory)
        self._items[descriptor.kind][descriptor.name] = factory
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

    def _load_entry_points(self) -> None:
        eps = entry_points()
        for kind, group in self.GROUPS.items():
            selected = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
            for ep in selected:
                loaded = ep.load()
                raw = getattr(loaded, "plugin_descriptor", None) or getattr(loaded, "descriptor", None)
                if raw is None:
                    raise ValueError(f"missing plugin descriptor v2 for {kind}:{ep.name}")
                descriptor = (
                    raw
                    if isinstance(raw, PluginDescriptor)
                    else PluginDescriptor.from_mapping(raw)
                    if isinstance(raw, Mapping)
                    else None
                )
                if descriptor is None or descriptor.kind != kind or descriptor.name != ep.name:
                    raise ValueError(f"invalid descriptor for plugin {kind}:{ep.name}")
                self._add(descriptor, loaded)

    def names(self, kind: str) -> list[str]:
        if kind not in self._items:
            raise KeyError(kind)
        return sorted(self._items[kind])

    def register(self, descriptor: PluginDescriptor, factory: Any) -> None:
        """Register an explicitly supplied plugin through the v2 validator."""

        self._add(descriptor, factory)

    def get(self, kind: str, name: str) -> Any:
        try:
            return self._items[kind][name]
        except KeyError as exc:
            raise KeyError(f"unknown {kind} plugin: {name}") from exc

    def descriptor(self, kind: str, name: str) -> PluginDescriptor:
        try:
            return self._descriptors[(kind, name)]
        except KeyError as exc:
            raise KeyError(f"unknown {kind} plugin: {name}") from exc

    def descriptors(self) -> list[PluginDescriptor]:
        return [self._descriptors[key] for key in sorted(self._descriptors)]

    def validate(self, selections: dict[str, list[str]] | None = None) -> None:
        target = selections or {kind: self.names(kind) for kind in self.GROUPS}
        for kind, names in sorted(target.items()):
            if kind not in self.GROUPS:
                raise KeyError(kind)
            for name in sorted(names):
                descriptor = self.descriptor(kind, name)
                if descriptor.contract_version != CONTRACT_VERSION:
                    raise ValueError(f"incompatible contract version for {kind}:{name}: {descriptor.contract_version}")
                validate_plugin_factory(descriptor, self.get(kind, name))

    def as_dict(self) -> list[dict[str, Any]]:
        return [descriptor.to_dict() for descriptor in self.descriptors()]


def default_catalog() -> PluginCatalog:
    return PluginCatalog()
