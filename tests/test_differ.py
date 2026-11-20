"""Unit tests for peppol_triage.differ."""

from __future__ import annotations

from pathlib import Path

import pytest

from peppol_triage.differ import diff_files, diff_json, diff_xml
from peppol_triage.models import DiffKind

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_diff_xml_ignores_whitespace_formatting() -> None:
    xml_a = '<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"><cbc:ID>INV-1</cbc:ID></Invoice>'
    xml_b = """<?xml version="1.0" encoding="UTF-8"?>
    <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
             xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
      <cbc:ID>  INV-1  </cbc:ID>
    </Invoice>
    """
    assert diff_xml(xml_a, xml_b) == []


def test_diff_xml_examples_detects_contract_and_value_changes() -> None:
    diffs = diff_files(
        EXAMPLES_DIR / "invoice_valid_ubl21.xml",
        EXAMPLES_DIR / "invoice_broken_totals.xml",
    )
    by_path = {d.path: d for d in diffs}

    assert "/Invoice/cac:AccountingCustomerParty/cac:Party/cbc:EndpointID/@schemeID" in by_path
    assert (
        by_path["/Invoice/cac:AccountingCustomerParty/cac:Party/cbc:EndpointID/@schemeID"].kind
        == DiffKind.REMOVED
    )
    assert "/Invoice/cac:LegalMonetaryTotal/cbc:LineExtensionAmount" in by_path
    assert (
        by_path["/Invoice/cac:LegalMonetaryTotal/cbc:LineExtensionAmount"].kind
        == DiffKind.VALUE_CHANGED
    )
    assert "/Invoice/cac:InvoiceLine[2]/cbc:LineExtensionAmount/@currencyID" in by_path
    assert (
        by_path["/Invoice/cac:InvoiceLine[2]/cbc:LineExtensionAmount/@currencyID"].after
        == "USD"
    )


def test_diff_json_ignores_key_order() -> None:
    a = {"b": 2, "a": {"y": 1, "x": 0}}
    b = {"a": {"x": 0, "y": 1}, "b": 2}
    assert diff_json(a, b) == []


def test_diff_json_examples_detects_all_change_kinds() -> None:
    diffs = diff_files(
        EXAMPLES_DIR / "invoice_v1.json",
        EXAMPLES_DIR / "invoice_v2_drift.json",
    )
    by_path = {d.path: d for d in diffs}

    assert by_path["$.currency"].kind == DiffKind.VALUE_CHANGED
    assert by_path["$.customer.schemeId"].kind == DiffKind.REMOVED
    assert by_path["$.lines[0].lineId"].kind == DiffKind.TYPE_CHANGED
    assert by_path["$.totals.roundingAmount"].kind == DiffKind.ADDED


def test_diff_files_rejects_mismatched_formats() -> None:
    with pytest.raises(ValueError, match="mismatched payload formats"):
        diff_files(
            EXAMPLES_DIR / "invoice_valid_ubl21.xml",
            EXAMPLES_DIR / "invoice_v1.json",
        )
