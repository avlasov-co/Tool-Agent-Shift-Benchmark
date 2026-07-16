from __future__ import annotations

import json
import sys
from pathlib import Path

from tool_agent_shift_benchmark.audit import AuditResult, AuditRunner, exit_code


def test_result_aggregation_and_json_serialization(tmp_path: Path) -> None:
    runner = AuditRunner(tmp_path, strict=True, python=sys.executable)
    runner.run_callable("pass", "pass check", lambda: (True, "ok"))
    runner.run_callable("fail", "fail check", lambda: (False, "broken"))
    report = runner.write_report()
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "failed"
    assert payload["checks"][0]["status"] == "passed"
    assert payload["checks"][1]["failure_explanation"] == "broken"


def test_timeout_handling_writes_a_failed_result(tmp_path: Path) -> None:
    runner = AuditRunner(tmp_path, python=sys.executable, timeout_seconds=1)
    result = runner.run_command("timeout", [sys.executable, "-c", "import time; time.sleep(2)"])
    assert result.status == "failed"
    assert "timed out" in (result.failure_explanation or "")
    assert Path(result.log_path).is_file()


def test_subprocess_failure_is_recorded(tmp_path: Path) -> None:
    runner = AuditRunner(tmp_path, python=sys.executable)
    result = runner.run_command("failure", [sys.executable, "-c", "raise SystemExit(3)"])
    assert result.status == "failed"
    assert result.failure_explanation == "command exited with status 3"


def test_skipped_check_is_serializable(tmp_path: Path) -> None:
    runner = AuditRunner(tmp_path, python=sys.executable)
    result = runner.skip("optional", "not installed")
    assert result.status == "skipped"
    assert json.loads(json.dumps(result.__dict__))["name"] == "optional"


def test_exit_codes_are_strict_only() -> None:
    failed = AuditResult("failure", "failed", 0.0, [], 1, "log", "broken")
    assert exit_code([failed], strict=False) == 0
    assert exit_code([failed], strict=True) == 1
