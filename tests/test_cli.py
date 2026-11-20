"""Unit tests for peppol_triage.cli and reporter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from peppol_triage.cli import main

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_cli_validate_valid_xml_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["validate", str(EXAMPLES_DIR / "invoice_valid_ubl21.xml")])
    captured = capsys.readouterr()
    assert code == 0
    assert "`PASS`" in captured.out


def test_cli_validate_broken_xml_json_format(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["validate", str(EXAMPLES_DIR / "invoice_broken_totals.xml"), "--format", "json"]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 1
    assert payload["valid"] is False
    assert payload["summary"]["errors"] >= 6


def test_cli_diff_json_detects_drift(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "diff",
            str(EXAMPLES_DIR / "invoice_v1.json"),
            str(EXAMPLES_DIR / "invoice_v2_drift.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "Semantic Contract Diff" in captured.out
    assert "$.lines[0].lineId" in captured.out


def test_cli_triage_writes_markdown_report(tmp_path: Path) -> None:
    out_file = tmp_path / "triage_report.md"
    code = main(
        [
            "triage",
            str(EXAMPLES_DIR / "invoice_broken_totals.xml"),
            "--reference",
            str(EXAMPLES_DIR / "invoice_valid_ubl21.xml"),
            "--out",
            str(out_file),
        ]
    )
    assert code == 1
    content = out_file.read_text(encoding="utf-8")
    assert "## Validation Findings" in content
    assert "## Semantic Contract Diff" in content
    assert "BR-CO-10" in content


def test_cli_missing_file_returns_two(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["validate", "/nonexistent/path/invoice.xml"])
    captured = capsys.readouterr()
    assert code == 2
    assert "Error:" in captured.err
