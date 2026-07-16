from __future__ import annotations

import csv
from pathlib import Path

from tool_agent_shift_benchmark.analysis.run_pairwise_compounds import (
    build_pairwise_compound_matrix,
    parse_pair,
    write_pairwise_compound_matrix,
)
from tool_agent_shift_benchmark.core.artifacts import ArtifactStore


def test_parse_pair_rejects_invalid_faults() -> None:
    assert parse_pair("schema_drift+missing_field") == ("schema_drift", "missing_field")
    try:
        parse_pair("normal+missing_field")
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("normal must not be accepted as a pairwise shifted fault")


def test_pairwise_compound_matrix_writes_rows(tmp_path: Path) -> None:
    config = tmp_path / "compound_matrix.yaml"
    config.write_text(
        """
schema_version: 2
episodes_per_combo: 1
seed: 7
fault_severities: [1.0]
environments:
  - file_ops
agents:
  - naive
fault_pairs:
  - schema_drift+missing_field
""".strip()
        + "\n",
        encoding="utf-8",
    )
    rows = build_pairwise_compound_matrix(str(config))
    assert len(rows) == 1
    row = rows[0]
    assert row["environment"] == "file_ops"
    assert row["agent"] == "naive"
    assert row["fault_pair"] == "schema_drift+missing_field"
    assert "pair_unsafe_action_rate" in row
    assert "delta_pair_vs_worst_single_unsafe_action_rate" in row

    store = ArtifactStore(tmp_path / "bundle")
    manifest = write_pairwise_compound_matrix(str(config), "analysis", artifact_store=store)
    assert manifest["rows"] == 1
    output = store.run_dir / manifest["output_csv"]
    assert output.exists()
    with output.open("r", newline="", encoding="utf-8") as f:
        written = list(csv.DictReader(f))
    assert written[0]["fault_pair"] == "schema_drift+missing_field"
