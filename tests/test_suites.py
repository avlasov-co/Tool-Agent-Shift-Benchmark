from __future__ import annotations

import json

import pytest

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.package_resources import builtin_suite_names, read_builtin_suite
from tool_agent_shift_benchmark.run_eval import run_eval
from tool_agent_shift_benchmark.suites import SuiteContract, validate_suite_bundle


def test_packaged_suite_contracts_have_stable_plans() -> None:
    expected = {"challenge": 120, "research": 3375, "smoke": 28, "standard": 240}
    assert set(builtin_suite_names()) == set(expected)
    for name, count in expected.items():
        contract = SuiteContract.load(name)
        assert contract.expected_plan_count == count
        assert len(contract.plan().episodes) == count


def test_challenge_contract_seals_outcomes_from_development() -> None:
    challenge = SuiteContract.load("challenge")
    assert challenge.scenario_split == "challenge"
    assert not challenge.challenge_outcomes_may_inform_development
    assert read_builtin_suite("challenge")["suite_version"] == "0.4.0"


def test_suite_manifest_parser_rejects_name_mismatch(monkeypatch) -> None:
    raw = read_builtin_suite("smoke")
    raw["name"] = "standard"
    monkeypatch.setattr("tool_agent_shift_benchmark.suites.read_builtin_suite", lambda _name: raw)
    with pytest.raises(ValueError, match="does not match"):
        SuiteContract.load("smoke")


def test_smoke_bundle_passes_durable_golden_checks(tmp_path) -> None:
    contract = SuiteContract.load("smoke")
    store = ArtifactStore(tmp_path / "smoke")
    run_eval(contract.config, contract.seed, artifact_store=store)
    store.finalize(command=["test", "smoke-suite"])

    report = validate_suite_bundle(contract, store.run_dir)

    assert report["status"] == "passed", json.dumps(report, indent=2)
    assert {row["name"] for row in report["checks"]} == set(contract.golden_checks)
