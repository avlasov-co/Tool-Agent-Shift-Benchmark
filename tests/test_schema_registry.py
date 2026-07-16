from __future__ import annotations

from dataclasses import replace
from random import Random

import pytest

from tool_agent_shift_benchmark.agents.validate_then_act import ValidateThenActAgent
from tool_agent_shift_benchmark.core.context import ObservationContext, redact_response_for_policy
from tool_agent_shift_benchmark.core.schema_registry import (
    SCHEMA_CHANGE_FAMILIES,
    SCHEMA_REGISTRY,
    SCHEMA_REGISTRY_CONTRACT,
    adapt_to_source_schema,
    apply_schema_delta,
)
from tool_agent_shift_benchmark.core.serialization import canonical_dumps
from tool_agent_shift_benchmark.core.types import AgentAction
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment
from tool_agent_shift_benchmark.faults.schema_drift import SchemaDriftFault
from tool_agent_shift_benchmark.monitors.schema import SchemaMonitor

ENVIRONMENTS = (FileOpsEnvironment, CalendarOpsEnvironment, RiskOpsEnvironment)


@pytest.mark.parametrize("environment_type", ENVIRONMENTS)
@pytest.mark.parametrize("family", SCHEMA_CHANGE_FAMILIES)
def test_every_schema_family_has_a_versioned_delta_in_every_environment(environment_type: type, family: str) -> None:
    environment = environment_type(seed=1201)
    clean = environment.tool_response()
    shifted = SchemaDriftFault(1.0, family=family).apply(clean, environment, Random(5))
    info = shifted.metadata["schema_info"]

    assert info["contract"] == SCHEMA_REGISTRY_CONTRACT
    assert info["source_schema"]["version"] == "v1"
    assert info["target_schema"]["version"] == shifted.observation.schema_version
    assert [change["family"] for change in info["schema_delta"]["changes"]] == [family]
    assert info["schema_delta"]["delta_hash"]
    assert canonical_dumps(shifted.to_dict())


@pytest.mark.parametrize("environment_type", ENVIRONMENTS)
@pytest.mark.parametrize("family", ("additive_field", "type_widening"))
def test_compatible_schema_changes_adapt_back_to_the_source(environment_type: type, family: str) -> None:
    environment = environment_type(seed=1211)
    clean = environment.tool_response()
    delta = SCHEMA_REGISTRY.delta(environment.name, severity=0.2, rng=Random(7), families=(family,))
    target = apply_schema_delta(clean.observation.data, delta)
    result = adapt_to_source_schema(target, delta)

    assert delta.compatibility_class == "compatible"
    assert result.succeeded
    assert result.data == clean.observation.data


@pytest.mark.parametrize("environment_type", ENVIRONMENTS)
@pytest.mark.parametrize("family", ("alias_rename", "nested_field_move", "unit_change"))
def test_repairable_schema_changes_have_explicit_reverse_migrations(environment_type: type, family: str) -> None:
    environment = environment_type(seed=1223)
    clean = environment.tool_response()
    delta = SCHEMA_REGISTRY.delta(environment.name, severity=0.7, rng=Random(11), families=(family,))
    target = apply_schema_delta(clean.observation.data, delta)
    result = adapt_to_source_schema(target, delta)

    assert delta.compatibility_class == "requires_adaptation"
    assert result.status == "repaired"
    assert result.repairs == (family,)
    assert result.data == clean.observation.data


def test_validating_agent_repairs_declared_alias_and_acts() -> None:
    environment = FileOpsEnvironment(seed=1231)
    shifted = SchemaDriftFault(1.0, family="alias_rename").apply(environment.tool_response(), environment, Random(13))
    context = ObservationContext.from_environment(environment, shifted.observation)
    decision = ValidateThenActAgent().decide(context, shifted)

    assert not decision.action.abstain
    assert decision.action.action_type == "inspect_files"
    assert decision.metadata["schema_adaptation"]["status"] == "repaired"


@pytest.mark.parametrize("family", ("required_field_removal", "breaking_type_change"))
def test_breaking_schema_changes_fail_closed_without_coercion(family: str) -> None:
    environment = FileOpsEnvironment(seed=1237)
    clean = environment.tool_response()
    shifted = SchemaDriftFault(1.0, family=family).apply(clean, environment, Random(17))
    context = ObservationContext.from_environment(environment, shifted.observation)
    decision = ValidateThenActAgent().decide(context, shifted)
    delta = SCHEMA_REGISTRY.delta(environment.name, severity=1.0, rng=Random(17), families=(family,))
    result = adapt_to_source_schema(apply_schema_delta(clean.observation.data, delta), delta)

    assert result.status == "failed"
    assert result.errors == (f"unsupported:{family}",)
    assert decision.action.abstain
    assert any(reason.startswith("schema_incompatible") for reason in decision.reasons)


def test_incorrect_unit_coercion_is_an_explicit_adaptation_failure() -> None:
    environment = FileOpsEnvironment(seed=1249)
    clean = environment.tool_response()
    delta = SCHEMA_REGISTRY.delta(environment.name, severity=0.8, rng=Random(19), families=("unit_change",))
    target = apply_schema_delta(clean.observation.data, delta)
    target["files"][0]["age_hours"] = "many"
    result = adapt_to_source_schema(target, delta)

    assert result.status == "failed"
    assert result.errors == ("age_hours_not_numeric",)


def test_schema_monitor_allows_declared_repairable_delta_and_blocks_breaking_delta() -> None:
    environment = FileOpsEnvironment(seed=1259)
    context = ObservationContext.from_environment(environment, environment.tool_response().observation)
    repairable = SchemaDriftFault(1.0, family="nested_field_move").apply(
        environment.tool_response(), environment, Random(23)
    )
    breaking = SchemaDriftFault(1.0, family="required_field_removal").apply(
        environment.tool_response(), environment, Random(23)
    )
    monitor = SchemaMonitor()

    allowed = monitor.check(context, repairable.observation, AgentAction("abstain", abstain=True))
    blocked = monitor.check(context, breaking.observation, AgentAction("abstain", abstain=True))

    assert allowed.allow_action
    assert allowed.metadata["compatibility_class"] == "requires_adaptation"
    assert not blocked.allow_action
    assert blocked.metadata["compatibility_class"] == "breaking"


def test_schema_information_is_intended_policy_data_without_fault_or_hidden_labels() -> None:
    environment = RiskOpsEnvironment(seed=1277)
    shifted = SchemaDriftFault(0.5).apply(environment.tool_response(), environment, Random(29))
    policy = redact_response_for_policy(shifted)
    payload = canonical_dumps(policy.to_dict())

    assert policy.metadata["schema_info"]["contract"] == SCHEMA_REGISTRY_CONTRACT
    assert policy.observation.metadata["schema_info"]["compatibility_class"] in {
        "compatible",
        "requires_adaptation",
        "breaking",
    }
    assert '"faults"' not in payload
    assert "hidden_ground_truth" not in payload


def test_severity_controls_schema_change_count_and_incompatibility() -> None:
    environment = FileOpsEnvironment(seed=1283)
    clean = environment.tool_response()
    low = SchemaDriftFault(0.1).apply(clean, environment, Random(31))
    medium = SchemaDriftFault(0.5).apply(clean, environment, Random(31))
    maximum = SchemaDriftFault(1.0).apply(clean, environment, Random(31))

    infos = [response.metadata["schema_info"] for response in (low, medium, maximum)]
    assert [len(info["schema_delta"]["changes"]) for info in infos] == [1, 4, 7]
    assert [info["compatibility_class"] for info in infos] == [
        "compatible",
        "requires_adaptation",
        "breaking",
    ]


def test_unknown_or_tampered_schema_delta_is_not_silently_trusted() -> None:
    environment = FileOpsEnvironment(seed=1291)
    shifted = SchemaDriftFault(1.0, family="alias_rename").apply(environment.tool_response(), environment, Random(37))
    tampered_info = dict(shifted.metadata["schema_info"])
    tampered_delta = dict(tampered_info["schema_delta"])
    tampered_delta["delta_hash"] = "schema_delta_tampered"
    tampered_info["schema_delta"] = tampered_delta
    tampered = replace(shifted, metadata={**shifted.metadata, "schema_info": tampered_info})
    decision = ValidateThenActAgent().decide(
        ObservationContext.from_environment(environment, tampered.observation),
        tampered,
    )

    assert decision.action.abstain
    assert "schema_drift_without_valid_registry_delta" in decision.reasons
