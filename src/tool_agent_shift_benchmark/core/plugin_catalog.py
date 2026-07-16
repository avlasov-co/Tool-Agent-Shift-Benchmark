"""Compatibility import for the platform plugin catalog."""

from .catalog import PluginCatalog, default_catalog
from .contracts import CONTRACT_VERSION, PluginDescriptor, TrustLevel

__all__ = ["PluginCatalog", "default_catalog", "PluginDescriptor", "TrustLevel", "CONTRACT_VERSION"]
