from __future__ import annotations

import pytest

from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.contracts import (
    CONTRACT_VERSION,
    PLUGIN_DESCRIPTOR_SCHEMA_VERSION,
    PluginDescriptor,
    TrustLevel,
    empty_configuration_schema,
    validate_configuration_schema,
)
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision


class ContractAgent:
    name = "contract_agent"
    version = "3.1.4"
    capabilities = ("visible-policy-v2",)
    configuration_schema = empty_configuration_schema()

    def decide(self, context, response):
        return AgentDecision(self.name, AgentAction("abstain", abstain=True), 1.0)


def descriptor(factory=ContractAgent, name: str = "contract_agent") -> PluginDescriptor:
    return PluginDescriptor.for_factory(
        "agent",
        name,
        factory,
        trust_level=TrustLevel.LOCAL_TRUSTED,
    )


def test_every_builtin_conforms_to_complete_v2_descriptor_and_interface() -> None:
    catalog = PluginCatalog(include_external=False)

    catalog.validate()

    assert {item.kind for item in catalog.descriptors()} == {
        "agent",
        "environment",
        "shift",
        "monitor",
        "evaluator",
    }
    for item in catalog.descriptors():
        assert item.schema_version == PLUGIN_DESCRIPTOR_SCHEMA_VERSION
        assert item.contract_version == CONTRACT_VERSION
        assert item.implementation_identifier.count(":") == 1
        assert item.configuration_hash.startswith("plugin_config_")
        assert item.trust_level is TrustLevel.BUILTIN_TRUSTED
        assert item.isolation_mode == "in_process"
        assert item.to_dict()["capabilities"] == list(item.capabilities)


def test_explicit_test_plugin_uses_the_same_validator_and_descriptor() -> None:
    catalog = PluginCatalog(include_external=False)
    item = descriptor()

    catalog.register(item, ContractAgent)
    catalog.validate({"agent": [ContractAgent.name]})

    assert catalog.get("agent", ContractAgent.name) is ContractAgent
    assert catalog.descriptor("agent", ContractAgent.name) == item


def test_missing_contract_method_is_rejected_at_registration() -> None:
    class MissingDecision:
        name = "missing_decision"

    item = descriptor(MissingDecision, MissingDecision.name)

    with pytest.raises(ValueError, match="missing decide contract method"):
        PluginCatalog(include_external=False).register(item, MissingDecision)


def test_implementation_identifier_mismatch_is_rejected() -> None:
    class DifferentImplementation(ContractAgent):
        name = ContractAgent.name

    with pytest.raises(ValueError, match="implementation identifier mismatch"):
        PluginCatalog(include_external=False).register(descriptor(), DifferentImplementation)


def test_v1_and_unknown_contract_versions_are_not_silently_adapted() -> None:
    value = descriptor().to_dict()
    value["contract_version"] = "1"

    with pytest.raises(ValueError, match="unsupported plugin contract version"):
        PluginDescriptor.from_mapping(value)


def test_malformed_configuration_schema_and_hash_are_rejected() -> None:
    with pytest.raises(ValueError, match="required plugin configuration property"):
        validate_configuration_schema(
            {
                **empty_configuration_schema(),
                "required": ["missing"],
            }
        )

    value = descriptor().to_dict()
    value["configuration_hash"] = "plugin_config_wrong"
    with pytest.raises(ValueError, match="configuration_hash does not match"):
        PluginDescriptor.from_mapping(value)


def test_duplicate_registration_is_deterministic_and_never_overwrites() -> None:
    catalog = PluginCatalog(include_external=False)
    item = descriptor()
    catalog.register(item, ContractAgent)

    with pytest.raises(ValueError, match="duplicate agent plugin identifier: contract_agent"):
        catalog.register(item, ContractAgent)

    assert catalog.get("agent", ContractAgent.name) is ContractAgent
