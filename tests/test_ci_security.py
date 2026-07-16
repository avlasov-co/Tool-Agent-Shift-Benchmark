from __future__ import annotations

import re
from pathlib import Path

WORKFLOW_DIR = Path(__file__).parents[1] / ".github" / "workflows"
SHA_PIN = re.compile(r"^\s*-\s+uses:\s+[^@\s]+@([0-9a-f]{40})\s+#\s+v\d", re.MULTILINE)


def test_all_workflow_actions_are_pinned_to_immutable_shas() -> None:
    workflow_paths = sorted(WORKFLOW_DIR.glob("*.yml"))
    assert workflow_paths
    for workflow in workflow_paths:
        contents = workflow.read_text(encoding="utf-8")
        uses_lines = [line for line in contents.splitlines() if line.strip().startswith("- uses:")]
        assert uses_lines, f"workflow has no actions: {workflow.name}"
        for line in uses_lines:
            assert SHA_PIN.match(line), f"mutable or undocumented action reference in {workflow.name}: {line}"


def test_workflows_default_to_read_only_and_avoid_privileged_pr_events() -> None:
    for workflow in WORKFLOW_DIR.glob("*.yml"):
        contents = workflow.read_text(encoding="utf-8")
        assert "pull_request_target" not in contents
        assert "permissions:" in contents
        assert "contents: read" in contents


def test_dependency_automation_and_security_expectations_are_present() -> None:
    dependabot = Path(__file__).parents[1] / ".github" / "dependabot.yml"
    security = Path(__file__).parents[1] / "SECURITY.md"

    assert dependabot.is_file()
    assert {"pip", "npm", "github-actions"} <= set(re.findall(r"package-ecosystem: (.+)", dependabot.read_text()))
    security_text = security.read_text(encoding="utf-8").lower()
    assert "secret scanning" in security_text
    assert "push protection" in security_text
