from __future__ import annotations

import json
import sys
from pathlib import Path

from tool_agent_shift_benchmark import audit
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


def _write_evidence_files(root: Path, *, bundle_path: str) -> None:
    ledger = root / "docs/metrics/claims-to-evidence-ledger.md"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        "| Claim ID | Proposed claim | Evidence unit | Required artifacts | Status |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| C001 | claim | unit | artifacts | verified |\n",
        encoding="utf-8",
    )
    references = {
        "schema_version": "claim-evidence-references-v1",
        "claims": [
            {
                "claim_id": "C001",
                "bundles": [
                    {
                        "path": bundle_path,
                        "run_id": "run_test",
                        "run_manifest_sha256": "a" * 64,
                        "finalization_sha256": "b" * 64,
                    }
                ],
            }
        ],
    }
    (root / "docs/metrics/verified-evidence.json").write_text(json.dumps(references), encoding="utf-8")


def test_claim_bound_evidence_does_not_require_historical_root_outputs(tmp_path: Path, monkeypatch) -> None:
    _write_evidence_files(tmp_path, bundle_path="runs/not-shipped")
    monkeypatch.chdir(tmp_path)
    passed, detail = audit._artifact_consistency()
    assert passed
    assert "not locally available" in detail
    assert "results/episodes.jsonl" not in detail


def test_claim_bound_evidence_warns_about_stale_root_material(tmp_path: Path, monkeypatch) -> None:
    _write_evidence_files(tmp_path, bundle_path="runs/not-shipped")
    (tmp_path / "results").mkdir()
    (tmp_path / "results/summary.csv").write_text("header\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    passed, detail = audit._artifact_consistency()
    assert passed
    assert "historical root evidence is partial" in detail
    assert "results/episodes.jsonl" in detail


def test_claim_bound_evidence_rejects_available_invalid_bundle(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "runs/bad"
    bundle.mkdir(parents=True)
    _write_evidence_files(tmp_path, bundle_path=str(bundle))
    monkeypatch.chdir(tmp_path)
    passed, detail = audit._artifact_consistency()
    assert not passed
    assert "not complete-valid" in detail


def test_claim_bound_evidence_requires_a_reference_for_every_verified_claim(tmp_path: Path, monkeypatch) -> None:
    _write_evidence_files(tmp_path, bundle_path="runs/not-shipped")
    ledger = tmp_path / "docs/metrics/claims-to-evidence-ledger.md"
    ledger.write_text(
        ledger.read_text(encoding="utf-8") + "| C002 | claim | unit | artifacts | verified |\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    passed, detail = audit._artifact_consistency()
    assert not passed
    assert "do not match ledger" in detail
