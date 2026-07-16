"""Compatibility import for the platform plugin catalog."""

from .catalog import (
    PLUGIN_DISCOVERY_CONTRACT,
    PluginCatalog,
    PluginDiscoveryError,
    PluginImportError,
    default_catalog,
)
from .contracts import CONTRACT_VERSION, PluginDescriptor, TrustLevel

__all__ = [
    "PluginCatalog",
    "PluginDiscoveryError",
    "PluginImportError",
    "default_catalog",
    "PluginDescriptor",
    "TrustLevel",
    "CONTRACT_VERSION",
    "PLUGIN_DISCOVERY_CONTRACT",
]
