"""Compatibility import for the platform plugin catalog."""
from .catalog import PluginCatalog, default_catalog
from .contracts import PluginDescriptor, CONTRACT_VERSION

__all__ = ["PluginCatalog", "default_catalog", "PluginDescriptor", "CONTRACT_VERSION"]
