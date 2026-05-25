from __future__ import annotations

from typing import Dict, Type

ENV_REGISTRY: Dict[str, type] = {}
AGENT_REGISTRY: Dict[str, type] = {}
FAULT_REGISTRY: Dict[str, type] = {}
MONITOR_REGISTRY: Dict[str, type] = {}


def register(registry: Dict[str, type], name: str, cls: type) -> None:
    if not name:
        raise ValueError("registry name must be non-empty")
    registry[name] = cls


def get(registry: Dict[str, type], name: str) -> type:
    if name not in registry:
        raise KeyError(f"unknown registry item: {name}")
    return registry[name]
