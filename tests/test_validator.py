"""Unit tests for peppol_triage.validator."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from peppol_triage.models import Severity
from peppol_triage.validator import validate_file, validate_xml_string

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_valid_ubl21_example_passes() -> None:
    issues = validate_file(EXAMPLES_DIR / "invoice_valid_ubl21.xml")
    assert issues == []


def test_broken_totals_example_catches_all_defects() -> None:
    issues = validate_file(EXAMPLES_DIR / "invoice_broken_totals.xml")
    rule_ids = {issue.rule_id for issue in issues}

    assert "PEPPOL-EN16931-R010-SCHEME" in rule_ids
    assert "PEPPOL-CURR-001" in rule_ids
    assert "BR-CO-10" in rule_ids
    assert "BR-CO-13" in rule_ids
    assert "BR-CO-15" in rule_ids
    assert "BR-CO-16" in rule_ids
    assert all(issue.severity == Severity.ERROR for issue in issues)


def test_missing_header_fields_and_bad_formats() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
             xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
      <cbc:IssueDate>20-11-2026</cbc:IssueDate>
      <cbc:InvoiceTypeCode>999</cbc:InvoiceTypeCode>
      <cbc:DocumentCurrencyCode>eur</cbc:DocumentCurrencyCode>
    </Invoice>
    """
    issues = validate_xml_string(xml)
    rule_ids = {issue.rule_id for issue in issues}

    assert "PEPPOL-EN16931-R004" in rule_ids
    assert "PEPPOL-BIS-BT23" in rule_ids
    assert "BR-02" in rule_ids
    assert "BR-03-FORMAT" in rule_ids
    assert "PEPPOL-EN16931-CL001" in rule_ids
    assert "BR-05-FORMAT" in rule_ids
    assert "PEPPOL-EN16931-R020" in rule_ids
    assert "PEPPOL-EN16931-R010" in rule_ids
    assert "BR-16" in rule_ids


def test_decimal_precision_with_allowances_and_prepaid() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
             xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
      <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
      <cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
      <cbc:ID>INV-DEC-01</cbc:ID>
      <cbc:IssueDate>2026-11-20</cbc:IssueDate>
      <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
      <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
      <cac:AccountingSupplierParty>
        <cac:Party><cbc:EndpointID schemeID="0088">123</cbc:EndpointID></cac:Party>
      </cac:AccountingSupplierParty>
      <cac:AccountingCustomerParty>
        <cac:Party><cbc:EndpointID schemeID="0088">456</cbc:EndpointID></cac:Party>
      </cac:AccountingCustomerParty>
      <cac:AllowanceCharge>
        <cbc:ChargeIndicator>false</cbc:ChargeIndicator>
        <cbc:Amount currencyID="EUR">0.05</cbc:Amount>
      </cac:AllowanceCharge>
      <cac:TaxTotal>
        <cbc:TaxAmount currencyID="EUR">0.05</cbc:TaxAmount>
      </cac:TaxTotal>
      <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="EUR">0.30</cbc:LineExtensionAmount>
        <cbc:TaxExclusiveAmount currencyID="EUR">0.25</cbc:TaxExclusiveAmount>
        <cbc:TaxInclusiveAmount currencyID="EUR">0.30</cbc:TaxInclusiveAmount>
        <cbc:PrepaidAmount currencyID="EUR">0.10</cbc:PrepaidAmount>
        <cbc:PayableAmount currencyID="EUR">0.20</cbc:PayableAmount>
      </cac:LegalMonetaryTotal>
      <cac:InvoiceLine>
        <cbc:ID>1</cbc:ID>
        <cbc:InvoicedQuantity unitCode="C62">1</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="EUR">0.10</cbc:LineExtensionAmount>
      </cac:InvoiceLine>
      <cac:InvoiceLine>
        <cbc:ID>2</cbc:ID>
        <cbc:InvoicedQuantity unitCode="C62">1</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="EUR">0.20</cbc:LineExtensionAmount>
      </cac:InvoiceLine>
    </Invoice>
    """
    issues = validate_xml_string(xml)
    assert issues == []


def test_malformed_xml_raises_parse_error() -> None:
    with pytest.raises(ET.ParseError):
        validate_xml_string("<Invoice><unclosed></Invoice>")
