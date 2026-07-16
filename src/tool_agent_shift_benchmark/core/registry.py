from __future__ import annotations

from typing import Dict

from tool_agent_shift_benchmark.core.contracts import PluginDescriptor, validate_plugin_factory

ENV_REGISTRY: Dict[str, type] = {}
AGENT_REGISTRY: Dict[str, type] = {}
FAULT_REGISTRY: Dict[str, type] = {}
MONITOR_REGISTRY: Dict[str, type] = {}


def register(registry: Dict[str, type], name: str, cls: type) -> None:
    if not name:
        raise ValueError("registry name must be non-empty")
    kind_by_registry = {
        id(ENV_REGISTRY): "environment",
        id(AGENT_REGISTRY): "agent",
        id(FAULT_REGISTRY): "shift",
        id(MONITOR_REGISTRY): "monitor",
    }
    kind = kind_by_registry.get(id(registry))
    if kind is None:
        raise ValueError("unknown plugin registry; use PluginCatalog.register")
    if name in registry:
        raise ValueError(f"duplicate {kind} plugin identifier: {name}")
    descriptor = PluginDescriptor.for_factory(kind, name, cls)
    validate_plugin_factory(descriptor, cls)
    registry[name] = cls


def get(registry: Dict[str, type], name: str) -> type:
    if name not in registry:
        raise KeyError(f"unknown registry item: {name}")
    return registry[name]
