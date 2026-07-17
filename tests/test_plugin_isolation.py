from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from isolation_plugin_fixtures import (
    CrashAgent,
    EnvironmentProbeAgent,
    ExcessiveOutputAgent,
    FilesystemProbeAgent,
    HonestIsolatedAgent,
    InfiniteLoopAgent,
    MalformedProtocolAgent,
    NetworkProbeAgent,
    StartupLoopAgent,
)
from tool_agent_shift_benchmark.analysis.run_analysis import build_agent_profiles
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.contracts import PluginDescriptor, TrustLevel
from tool_agent_shift_benchmark.core.isolation import (
    BOUNDED_SUBPROCESS_ISOLATION_MODE,
    ISOLATION_MANIFEST_CONTRACT,
    IsolatedPluginFactory,
)
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.metrics.aggregation import aggregate
from tool_agent_shift_benchmark.reporting.report import _rows, generate_markdown_report


def _descriptor(factory: Any) -> PluginDescriptor:
    return PluginDescriptor.for_factory(
        "agent",
        factory.name,
        factory,
        trust_level=TrustLevel.UNTRUSTED_ISOLATED,
        metadata={
            "isolation": {
                "startup_timeout_seconds": 3.0,
                "call_timeout_seconds": 0.25,
                "output_limit_bytes": 4096,
                "memory_limit_mb": 512,
                "cpu_limit_seconds": 5,
                "file_size_limit_bytes": 4096,
                "open_files_limit": 64,
                "process_limit": 8,
            }
        },
    )


def _coordinator(factory: Any) -> RunCoordinator:
    descriptor = _descriptor(factory)
    catalog = PluginCatalog(include_external=False)
    catalog.register(descriptor, factory)
    spec = ExperimentSpec.from_config(
        {
            "schema_version": 2,
            "environments": ["file_ops"],
            "agents": [factory.name],
            "faults": ["normal"],
            "episodes_per_combo": 1,
            "episode_steps": 1,
            "failure_policy": "continue",
            "plugin_references": [
                {
                    "kind": "agent",
                    "name": factory.name,
                    "version": descriptor.version,
                    "contract_version": descriptor.contract_version,
                    "entry_point": descriptor.implementation_identifier,
                }
            ],
        },
        seed=1701,
    )
    return RunCoordinator(spec, catalog)


def test_restricted_factory_runs_in_child_with_manifest_and_visible_callback() -> None:
    descriptor = _descriptor(HonestIsolatedAgent)
    catalog = PluginCatalog(include_external=False)
    catalog.register(descriptor, HonestIsolatedAgent)
    isolated = catalog.get("agent", HonestIsolatedAgent.name)

    assert isinstance(isolated, IsolatedPluginFactory)
    assert descriptor.isolation_mode == BOUNDED_SUBPROCESS_ISOLATION_MODE
    instance = isolated()
    try:
        assert instance.isolation_manifest["contract"] == ISOLATION_MANIFEST_CONTRACT
        assert instance.isolation_manifest["pid"] != os.getpid()
        assert instance.isolation_manifest["network_policy"] == "python_audit_deny_best_effort"
    finally:
        instance.close()

    coordinator = _coordinator(HonestIsolatedAgent)
    episode = coordinator.run()[0]
    assert episode.decision.reasons == ("visible_callback_succeeded",)
    assert episode.decision.metadata["worker_pid"] != os.getpid()
    assert episode.planned_identity["agent"]["isolation_mode"] == BOUNDED_SUBPROCESS_ISOLATION_MODE
    agent_manifest = next(
        item for item in episode.metadata["plugin_isolation"]["components"] if item["component"]["kind"] == "agent"
    )
    assert agent_manifest["runtime"]["mode"] == BOUNDED_SUBPROCESS_ISOLATION_MODE
    assert "pid" not in agent_manifest["runtime"]


@pytest.mark.parametrize(
    ("factory", "error_type", "phase"),
    (
        (StartupLoopAgent, "PluginStartupTimeout", "plugin_startup_timeout"),
        (InfiniteLoopAgent, "PluginCallTimeout", "plugin_call_timeout"),
        (ExcessiveOutputAgent, "PluginOutputLimitError", "plugin_output_limit"),
        (CrashAgent, "PluginProcessCrash", "plugin_process_crash"),
        (MalformedProtocolAgent, "PluginProtocolViolation", "plugin_protocol_violation"),
    ),
)
def test_adversarial_process_failures_are_bounded_and_structured(factory, error_type: str, phase: str) -> None:
    coordinator = _coordinator(factory)
    started = time.monotonic()

    assert coordinator.run() == []

    assert time.monotonic() - started < 5.0
    assert len(coordinator.errors) == 1
    error = coordinator.errors[0]
    assert error.error_type == error_type
    assert error.phase == phase
    assert error.planned_episode is not None
    assert error.action_record is not None
    assert error.action_record["status"] == "infrastructure_failure"


def test_filesystem_probe_is_confined_to_private_cwd() -> None:
    episode = _coordinator(FilesystemProbeAgent).run()[0]
    metadata = episode.decision.metadata

    assert metadata["outside_read_denied"] is True
    assert metadata["private_write_succeeded"] is True
    assert Path(str(metadata["cwd"])).name.startswith("tasb-plugin-")


def test_parent_credentials_and_arbitrary_environment_are_not_inherited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASB_PARENT_SECRET", "must-not-cross")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-cross")

    metadata = _coordinator(EnvironmentProbeAgent).run()[0].decision.metadata

    assert metadata["parent_secret"] is None
    assert metadata["aws_key"] is None
    assert "TASB_PARENT_SECRET" not in metadata["environment_keys"]
    assert "AWS_SECRET_ACCESS_KEY" not in metadata["environment_keys"]
    assert Path(str(metadata["home"])).name.startswith("tasb-plugin-")


def test_python_network_probe_is_denied() -> None:
    metadata = _coordinator(NetworkProbeAgent).run()[0].decision.metadata
    assert metadata["network_denied"] is True


def test_failed_episode_remains_in_aggregate_denominator() -> None:
    coordinator = _coordinator(CrashAgent)
    episodes = coordinator.run()

    rows = aggregate(episodes, coordinator.errors)

    assert len(rows) == 1
    row = rows[0]
    assert row["planned_episodes"] == 1.0
    assert row["completed_episodes"] == 0.0
    assert row["infrastructure_failures"] == 1.0
    assert row["task_success_rate"] == 0.0
    assert row["unsafe_or_failed_rate"] == 1.0
    assert row["safe_completion_rate"] == 0.0


def test_report_fallback_retains_failed_episode_denominator(tmp_path: Path) -> None:
    coordinator = _coordinator(CrashAgent)
    assert coordinator.run() == []
    results = tmp_path / "results"
    results.mkdir()
    (results / "episodes.jsonl").write_text("", encoding="utf-8")
    (results / "orchestration_errors.jsonl").write_text(
        "\n".join(json.dumps(error.to_dict()) for error in coordinator.errors) + "\n",
        encoding="utf-8",
    )

    rows = _rows(results / "summary.csv")

    assert len(rows) == 1
    assert rows[0]["planned_episodes"] == 1.0
    assert rows[0]["infrastructure_failures"] == 1.0

    profiles = build_agent_profiles(results)
    assert len(profiles) == 1
    assert profiles[0]["planned_episodes"] == 1
    assert profiles[0]["completed_episodes"] == 0
    assert profiles[0]["infrastructure_failures"] == 1
    assert profiles[0]["unsafe_or_failed_rate"] == 1.0

    report_path = tmp_path / "report.md"
    with pytest.raises(ValueError, match="complete-valid"):
        generate_markdown_report(results / "summary.csv", report_path)
    assert not report_path.exists()
