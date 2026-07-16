from __future__ import annotations

import pytest

from tool_agent_shift_benchmark.agents.offline_llm_fixture import OfflineLLMFixtureAgent, PolicyResourceError
from tool_agent_shift_benchmark.core.config import load_config
from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.serialization import canonical_dumps, canonical_loads
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.package_resources import (
    BuiltinResourceError,
    builtin_config_names,
    read_builtin_config,
    read_builtin_resource,
)


def test_packaged_named_configs_and_explicit_external_paths(tmp_path) -> None:
    assert {"small", "full", "compound_matrix"} <= set(builtin_config_names())
    builtin = load_config("small")
    assert builtin["schema_version"] == 2
    assert "offline_llm_fixture" in builtin["policy_resources"]

    external = tmp_path / "external.yaml"
    external.write_text(read_builtin_config("small")[1], encoding="utf-8")
    assert load_config(external) == builtin


def test_fixture_policy_contents_change_visible_decisions(tmp_path) -> None:
    env = FileOpsEnvironment(seed=1, scenario_index=0)
    response = env.tool_response()
    context = ObservationContext.from_environment(env, response.observation)
    baseline = OfflineLLMFixtureAgent().decide(context, response)
    assert not baseline.action.abstain
    assert baseline.metadata["policy_version"] == "1.0.0"
    assert len(baseline.metadata["policy_sha256"]) == 64

    custom = canonical_loads(read_builtin_resource("policies", "offline_llm_policy.json").decode("utf-8"))
    custom["policy_version"] = "test-policy"
    custom["clean_action"] = {"mode": "abstain", "confidence": 0.3, "reason": "test_clean_abstain"}
    policy_path = tmp_path / "changed-policy.json"
    policy_path.write_text(canonical_dumps(custom, pretty=True), encoding="utf-8")
    changed = OfflineLLMFixtureAgent(policy_path).decide(context, response)

    assert changed.action.abstain
    assert changed.action.reason == "test_clean_abstain"
    assert changed.metadata["policy_version"] == "test-policy"
    assert changed.metadata["policy_sha256"] != baseline.metadata["policy_sha256"]


def test_missing_or_malformed_fixture_policy_fails_clearly(tmp_path) -> None:
    with pytest.raises(PolicyResourceError, match="does not exist"):
        OfflineLLMFixtureAgent(tmp_path / "missing.json")

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{}", encoding="utf-8")
    with pytest.raises(PolicyResourceError, match="unknown or missing"):
        OfflineLLMFixtureAgent(malformed)

    with pytest.raises(BuiltinResourceError, match="missing"):
        read_builtin_resource("policies", "missing.json")
