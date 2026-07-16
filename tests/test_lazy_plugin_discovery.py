from __future__ import annotations

from typing import Any

import pytest

from tool_agent_shift_benchmark.core.catalog import (
    PLUGIN_DESCRIPTOR_METADATA_FIELD,
    PLUGIN_DESCRIPTOR_METADATA_FILE,
    PluginCatalog,
    PluginDiscoveryError,
    PluginImportError,
)
from tool_agent_shift_benchmark.core.contracts import PluginDescriptor, TrustLevel
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision


class ExternalAgent:
    name = "lazy_external"
    version = "7.0.0"
    capabilities: tuple[str, ...] = ()

    def decide(self, context, response):
        return AgentDecision(self.name, AgentAction("abstain", abstain=True), 1.0)


class FakeEntryPoint:
    def __init__(
        self,
        name: str,
        value: str,
        descriptor: Any = None,
        *,
        group: str = "tasb.agents",
        factory: Any = ExternalAgent,
        error: Exception | None = None,
        distribution_payload: Any = None,
    ):
        self.name = name
        self.value = value
        self.group = group
        self.factory = factory
        self.error = error
        self.load_count = 0
        if descriptor is not None:
            self.tasb_plugin_descriptor = descriptor
        if distribution_payload is not None:
            self.dist = FakeDistribution(distribution_payload)

    def load(self):
        self.load_count += 1
        if self.error is not None:
            raise self.error
        return self.factory


class FakeEntryPoints:
    def __init__(self, entries: tuple[FakeEntryPoint, ...]):
        self.entries = entries

    def select(self, *, group: str):
        return [entry for entry in self.entries if entry.group == group]


class FakeMetadata:
    def get_all(self, name: str):
        return []


class FakeDistribution:
    metadata = FakeMetadata()

    def __init__(self, payload: Any):
        self.payload = payload

    def read_text(self, name: str):
        assert name == PLUGIN_DESCRIPTOR_METADATA_FILE
        import json

        return json.dumps(self.payload)


def descriptor(factory: Any = ExternalAgent, *, name: str | None = None) -> dict[str, Any]:
    return PluginDescriptor.for_factory(
        "agent",
        name or factory.name,
        factory,
        trust_level=TrustLevel.EXTERNAL_RESTRICTED,
    ).to_dict()


def install_fake_entry_points(monkeypatch: pytest.MonkeyPatch, *entries: FakeEntryPoint) -> None:
    monkeypatch.setattr(
        "tool_agent_shift_benchmark.core.catalog.entry_points",
        lambda: FakeEntryPoints(tuple(entries)),
    )


def test_metadata_listing_and_validation_never_import_entry_point_code(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = descriptor()
    trap = FakeEntryPoint(
        ExternalAgent.name,
        payload["implementation_identifier"],
        error=AssertionError("entry-point import trap executed"),
        distribution_payload=[payload],
    )
    install_fake_entry_points(monkeypatch, trap)

    catalog = PluginCatalog()

    assert ExternalAgent.name in catalog.names("agent")
    assert catalog.descriptor("agent", ExternalAgent.name).version == ExternalAgent.version
    assert any(item.name == ExternalAgent.name for item in catalog.descriptors())
    assert any(item["name"] == ExternalAgent.name for item in catalog.as_dict())
    catalog.validate()
    assert catalog.get("agent", "naive")
    assert trap.load_count == 0


def test_only_an_explicitly_requested_plugin_is_loaded_and_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = descriptor()
    entry = FakeEntryPoint(ExternalAgent.name, payload["implementation_identifier"], payload)
    install_fake_entry_points(monkeypatch, entry)
    catalog = PluginCatalog()

    assert catalog.get("agent", ExternalAgent.name) is ExternalAgent
    assert catalog.get("agent", ExternalAgent.name) is ExternalAgent
    assert entry.load_count == 1
    catalog.validate({"agent": [ExternalAgent.name]})
    assert entry.load_count == 1


def test_import_failure_is_scoped_cached_and_does_not_break_unrelated_plugins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = descriptor()
    broken = FakeEntryPoint(
        ExternalAgent.name,
        payload["implementation_identifier"],
        payload,
        error=RuntimeError("import exploded"),
    )
    install_fake_entry_points(monkeypatch, broken)
    catalog = PluginCatalog()

    assert catalog.get("agent", "naive")
    with pytest.raises(PluginImportError, match="failed to import requested agent plugin lazy_external"):
        catalog.get("agent", ExternalAgent.name)
    with pytest.raises(PluginImportError, match="failed to import requested agent plugin lazy_external"):
        catalog.get("agent", ExternalAgent.name)
    assert broken.load_count == 1
    assert catalog.get("environment", "file_ops")


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda value: {**value, "contract_version": "999"}, "unsupported plugin contract version"),
        (lambda value: {**value, "implementation_identifier": "wrong.module:Agent"}, "implementation mismatch"),
    ),
)
def test_invalid_static_descriptor_is_a_scoped_metadata_error(
    monkeypatch: pytest.MonkeyPatch,
    mutation,
    message: str,
) -> None:
    payload = descriptor()
    invalid = mutation(payload)
    entry = FakeEntryPoint(ExternalAgent.name, payload["implementation_identifier"], invalid)
    install_fake_entry_points(monkeypatch, entry)
    catalog = PluginCatalog()

    assert catalog.get("agent", "naive")
    assert catalog.discovery_errors()[0]["name"] == ExternalAgent.name
    with pytest.raises(PluginDiscoveryError, match=message):
        catalog.descriptor("agent", ExternalAgent.name)
    with pytest.raises(PluginDiscoveryError, match=message):
        catalog.validate()
    assert entry.load_count == 0


def test_missing_descriptor_and_duplicates_are_deterministic_without_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = descriptor()
    missing = FakeEntryPoint("missing_metadata", "example.plugin:Missing")
    first = FakeEntryPoint(ExternalAgent.name, payload["implementation_identifier"], payload)
    second = FakeEntryPoint(ExternalAgent.name, payload["implementation_identifier"], payload)
    install_fake_entry_points(monkeypatch, second, missing, first)
    catalog = PluginCatalog()

    errors = {(item["kind"], item["name"]): item["error"] for item in catalog.discovery_errors()}
    assert PLUGIN_DESCRIPTOR_METADATA_FIELD in errors[("agent", "missing_metadata")]
    assert errors[("agent", ExternalAgent.name)] == "duplicate agent plugin identifier: lazy_external"
    with pytest.raises(PluginDiscoveryError, match="duplicate agent plugin identifier"):
        catalog.get("agent", ExternalAgent.name)
    assert first.load_count == second.load_count == missing.load_count == 0
