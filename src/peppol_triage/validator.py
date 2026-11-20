"""Deterministic UBL 2.1 / PEPPOL BIS Billing 3.0 XML validator."""

from __future__ import annotations

import datetime
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

from peppol_triage.models import Severity, ValidationIssue

UBL_INVOICE_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CBC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"

NS = {
    "inv": UBL_INVOICE_NS,
    "cbc": CBC_NS,
    "cac": CAC_NS,
}

PEPPOL_BIS3_CUSTOMIZATION_ID = (
    "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
)
VALID_INVOICE_TYPE_CODES = frozenset({"380", "381", "383", "384", "386", "389", "751"})
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def _split_tag(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{") and "}" in tag:
        ns, local = tag[1:].split("}", 1)
        return ns, local
    return None, tag


def _format_tag(tag: str) -> str:
    ns, local = _split_tag(tag)
    if ns == UBL_INVOICE_NS:
        return local
    if ns == CBC_NS:
        return f"cbc:{local}"
    if ns == CAC_NS:
        return f"cac:{local}"
    if ns:
        return f"{{{ns}}}{local}"
    return local


def _text(el: ET.Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    stripped = el.text.strip()
    return stripped if stripped else None


def _parse_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(raw.strip())
    except InvalidOperation:
        return None


def _check_required_text(
    root: ET.Element,
    xpath_query: str,
    display_xpath: str,
    rule_id: str,
    label: str,
    issues: list[ValidationIssue],
    suggestion: str,
) -> str | None:
    el = root.find(xpath_query, NS)
    val = _text(el)
    if val is None:
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                severity=Severity.ERROR,
                xpath=display_xpath,
                message=f"Missing or empty mandatory element: {label}.",
                expected="Non-empty value",
                actual="<missing>",
                suggestion=suggestion,
            )
        )
        return None
    return val


def _check_endpoint(
    root: ET.Element,
    party_tag: str,
    role: str,
    rule_id: str,
    issues: list[ValidationIssue],
) -> None:
    endpoint = root.find(f"cac:{party_tag}/cac:Party/cbc:EndpointID", NS)
    xpath = f"/Invoice/cac:{party_tag}/cac:Party/cbc:EndpointID"
    val = _text(endpoint)
    if val is None:
        issues.append(
            ValidationIssue(
                rule_id=rule_id,
                severity=Severity.ERROR,
                xpath=xpath,
                message=f"Missing {role} electronic address (EndpointID).",
                expected="Non-empty EndpointID with @schemeID",
                actual="<missing>",
                suggestion=f"Add <cbc:EndpointID schemeID=\"...\"> inside {party_tag}/cac:Party.",
            )
        )
        return

    scheme_id = (endpoint.attrib.get("schemeID") or "").strip() if endpoint is not None else ""
    if not scheme_id:
        issues.append(
            ValidationIssue(
                rule_id=f"{rule_id}-SCHEME",
                severity=Severity.ERROR,
                xpath=f"{xpath}/@schemeID",
                message=f"{role} EndpointID is missing required @schemeID attribute.",
                expected="Valid EAS schemeID (e.g., 0088, 0192, 9930)",
                actual="<missing>",
                suggestion="Add schemeID attribute from the PEPPOL Electronic Address Scheme (EAS) list.",
            )
        )


def _check_currency_consistency(
    root: ET.Element,
    doc_currency: str | None,
    issues: list[ValidationIssue],
) -> None:
    if not doc_currency:
        return

    def walk(node: ET.Element, current_path: str) -> None:
        counts: dict[str, int] = {}
        for child in node:
            label = _format_tag(child.tag)
            counts[label] = counts.get(label, 0) + 1

        seen: dict[str, int] = {}
        for child in node:
            label = _format_tag(child.tag)
            seen[label] = seen.get(label, 0) + 1
            suffix = f"[{seen[label]}]" if counts[label] > 1 else ""
            child_path = f"{current_path}/{label}{suffix}"

            curr = child.attrib.get("currencyID")
            if curr is not None and curr.strip() != doc_currency:
                issues.append(
                    ValidationIssue(
                        rule_id="PEPPOL-CURR-001",
                        severity=Severity.ERROR,
                        xpath=f"{child_path}/@currencyID",
                        message="Element currencyID does not match DocumentCurrencyCode.",
                        expected=doc_currency,
                        actual=curr.strip() or "<empty>",
                        suggestion=f"Align @currencyID to '{doc_currency}'.",
                    )
                )
            walk(child, child_path)

    walk(root, "/Invoice")


def _check_arithmetic(root: ET.Element, issues: list[ValidationIssue]) -> None:
    lines = root.findall("cac:InvoiceLine", NS)
    line_sum = Decimal("0")
    line_sum_valid = True

    for idx, line in enumerate(lines, start=1):
        line_xpath = f"/Invoice/cac:InvoiceLine[{idx}]"
        _check_required_text(
            line,
            "cbc:ID",
            f"{line_xpath}/cbc:ID",
            "BR-21",
            "Invoice line identifier (BT-126)",
            issues,
            "Provide a unique <cbc:ID> on every InvoiceLine.",
        )

        qty_el = line.find("cbc:InvoicedQuantity", NS)
        qty_val = _parse_decimal(_text(qty_el))
        if qty_val is None:
            issues.append(
                ValidationIssue(
                    rule_id="BR-22",
                    severity=Severity.ERROR,
                    xpath=f"{line_xpath}/cbc:InvoicedQuantity",
                    message="Missing or non-numeric InvoicedQuantity.",
                    expected="Decimal number",
                    actual=_text(qty_el) or "<missing>",
                    suggestion="Set <cbc:InvoicedQuantity unitCode=\"...\"> to a valid decimal.",
                )
            )
        elif not (qty_el is not None and (qty_el.attrib.get("unitCode") or "").strip()):
            issues.append(
                ValidationIssue(
                    rule_id="BR-23",
                    severity=Severity.ERROR,
                    xpath=f"{line_xpath}/cbc:InvoicedQuantity/@unitCode",
                    message="InvoicedQuantity is missing required @unitCode attribute.",
                    expected="UNECE Rec 20 unitCode (e.g., C62, EA, HUR)",
                    actual="<missing>",
                    suggestion="Add unitCode attribute to <cbc:InvoicedQuantity>.",
                )
            )

        ext_el = line.find("cbc:LineExtensionAmount", NS)
        ext_val = _parse_decimal(_text(ext_el))
        if ext_val is None:
            line_sum_valid = False
            issues.append(
                ValidationIssue(
                    rule_id="BR-24",
                    severity=Severity.ERROR,
                    xpath=f"{line_xpath}/cbc:LineExtensionAmount",
                    message="Missing or non-numeric line LineExtensionAmount.",
                    expected="Decimal monetary amount",
                    actual=_text(ext_el) or "<missing>",
                    suggestion="Provide a valid decimal <cbc:LineExtensionAmount>.",
                )
            )
        else:
            line_sum += ext_val

    lmt = root.find("cac:LegalMonetaryTotal", NS)
    if lmt is None:
        issues.append(
            ValidationIssue(
                rule_id="BR-13",
                severity=Severity.ERROR,
                xpath="/Invoice/cac:LegalMonetaryTotal",
                message="Missing mandatory cac:LegalMonetaryTotal aggregate.",
                expected="cac:LegalMonetaryTotal element",
                actual="<missing>",
                suggestion="Add <cac:LegalMonetaryTotal> with LineExtensionAmount, TaxExclusiveAmount, TaxInclusiveAmount, and PayableAmount.",
            )
        )
        return

    lmt_line_ext = _parse_decimal(_text(lmt.find("cbc:LineExtensionAmount", NS)))
    lmt_tax_excl = _parse_decimal(_text(lmt.find("cbc:TaxExclusiveAmount", NS)))
    lmt_tax_incl = _parse_decimal(_text(lmt.find("cbc:TaxInclusiveAmount", NS)))
    lmt_payable = _parse_decimal(_text(lmt.find("cbc:PayableAmount", NS)))
    lmt_prepaid = _parse_decimal(_text(lmt.find("cbc:PrepaidAmount", NS))) or Decimal("0")
    lmt_rounding = _parse_decimal(_text(lmt.find("cbc:PayableRoundingAmount", NS))) or Decimal("0")

    # BR-CO-10: Sum of line net amounts == LegalMonetaryTotal/LineExtensionAmount
    if lines and line_sum_valid and lmt_line_ext is not None:
        if line_sum != lmt_line_ext:
            issues.append(
                ValidationIssue(
                    rule_id="BR-CO-10",
                    severity=Severity.ERROR,
                    xpath="/Invoice/cac:LegalMonetaryTotal/cbc:LineExtensionAmount",
                    message="Sum of InvoiceLine/LineExtensionAmount does not equal LegalMonetaryTotal/LineExtensionAmount.",
                    expected=str(line_sum),
                    actual=str(lmt_line_ext),
                    suggestion=f"Update LegalMonetaryTotal/cbc:LineExtensionAmount to {line_sum}.",
                )
            )
    elif lmt_line_ext is None:
        issues.append(
            ValidationIssue(
                rule_id="BR-12",
                severity=Severity.ERROR,
                xpath="/Invoice/cac:LegalMonetaryTotal/cbc:LineExtensionAmount",
                message="Missing or non-numeric LegalMonetaryTotal/LineExtensionAmount.",
                expected="Decimal monetary amount",
                actual=_text(lmt.find("cbc:LineExtensionAmount", NS)) or "<missing>",
                suggestion="Provide <cbc:LineExtensionAmount> inside cac:LegalMonetaryTotal.",
            )
        )

    # Document-level allowances & charges for BR-CO-13
    doc_allowances = Decimal("0")
    doc_charges = Decimal("0")
    for ac in root.findall("cac:AllowanceCharge", NS):
        indicator = (_text(ac.find("cbc:ChargeIndicator", NS)) or "").lower()
        amt = _parse_decimal(_text(ac.find("cbc:Amount", NS)))
        if amt is not None:
            if indicator == "true":
                doc_charges += amt
            elif indicator == "false":
                doc_allowances += amt

    if lmt_line_ext is not None and lmt_tax_excl is not None:
        expected_tax_excl = lmt_line_ext - doc_allowances + doc_charges
        if expected_tax_excl != lmt_tax_excl:
            issues.append(
                ValidationIssue(
                    rule_id="BR-CO-13",
                    severity=Severity.ERROR,
                    xpath="/Invoice/cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount",
                    message="TaxExclusiveAmount does not match LineExtensionAmount - Allowances + Charges.",
                    expected=str(expected_tax_excl),
                    actual=str(lmt_tax_excl),
                    suggestion=f"Update LegalMonetaryTotal/cbc:TaxExclusiveAmount to {expected_tax_excl}.",
                )
            )
    elif lmt_tax_excl is None:
        issues.append(
            ValidationIssue(
                rule_id="BR-13-TAX-EXCL",
                severity=Severity.ERROR,
                xpath="/Invoice/cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount",
                message="Missing or non-numeric LegalMonetaryTotal/TaxExclusiveAmount.",
                expected="Decimal monetary amount",
                actual="<missing>",
                suggestion="Provide <cbc:TaxExclusiveAmount> inside cac:LegalMonetaryTotal.",
            )
        )

    # Document-level TaxTotal
    tax_total_el = root.find("cac:TaxTotal", NS)
    tax_amount: Decimal | None = None
    if tax_total_el is not None:
        tax_amount = _parse_decimal(_text(tax_total_el.find("cbc:TaxAmount", NS)))
        subtotals = tax_total_el.findall("cac:TaxSubtotal", NS)
        if subtotals and tax_amount is not None:
            sub_tax_sum = Decimal("0")
            sub_taxable_sum = Decimal("0")
            sub_valid = True
            for sub in subtotals:
                s_tax = _parse_decimal(_text(sub.find("cbc:TaxAmount", NS)))
                s_taxable = _parse_decimal(_text(sub.find("cbc:TaxableAmount", NS)))
                if s_tax is None or s_taxable is None:
                    sub_valid = False
                    break
                sub_tax_sum += s_tax
                sub_taxable_sum += s_taxable

            if sub_valid:
                if sub_tax_sum != tax_amount:
                    issues.append(
                        ValidationIssue(
                            rule_id="BR-CO-14",
                            severity=Severity.ERROR,
                            xpath="/Invoice/cac:TaxTotal/cbc:TaxAmount",
                            message="TaxTotal/TaxAmount does not equal sum of TaxSubtotal/TaxAmount.",
                            expected=str(sub_tax_sum),
                            actual=str(tax_amount),
                            suggestion=f"Update TaxTotal/cbc:TaxAmount to {sub_tax_sum}.",
                        )
                    )
                if lmt_tax_excl is not None and sub_taxable_sum != lmt_tax_excl:
                    issues.append(
                        ValidationIssue(
                            rule_id="BR-S-08",
                            severity=Severity.ERROR,
                            xpath="/Invoice/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount",
                            message="Sum of TaxSubtotal/TaxableAmount does not equal LegalMonetaryTotal/TaxExclusiveAmount.",
                            expected=str(lmt_tax_excl),
                            actual=str(sub_taxable_sum),
                            suggestion=f"Align TaxSubtotal/cbc:TaxableAmount sum to {lmt_tax_excl}.",
                        )
                    )

    # BR-CO-15: TaxExclusiveAmount + TaxAmount == TaxInclusiveAmount
    if lmt_tax_excl is not None and tax_amount is not None and lmt_tax_incl is not None:
        expected_tax_incl = lmt_tax_excl + tax_amount
        if expected_tax_incl != lmt_tax_incl:
            issues.append(
                ValidationIssue(
                    rule_id="BR-CO-15",
                    severity=Severity.ERROR,
                    xpath="/Invoice/cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount",
                    message="TaxInclusiveAmount does not equal TaxExclusiveAmount + TaxTotal/TaxAmount.",
                    expected=str(expected_tax_incl),
                    actual=str(lmt_tax_incl),
                    suggestion=f"Update LegalMonetaryTotal/cbc:TaxInclusiveAmount to {expected_tax_incl}.",
                )
            )
    elif lmt_tax_incl is None:
        issues.append(
            ValidationIssue(
                rule_id="BR-14",
                severity=Severity.ERROR,
                xpath="/Invoice/cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount",
                message="Missing or non-numeric LegalMonetaryTotal/TaxInclusiveAmount.",
                expected="Decimal monetary amount",
                actual="<missing>",
                suggestion="Provide <cbc:TaxInclusiveAmount> inside cac:LegalMonetaryTotal.",
            )
        )

    # BR-CO-16: TaxInclusiveAmount - PrepaidAmount + PayableRoundingAmount == PayableAmount
    if lmt_tax_incl is not None and lmt_payable is not None:
        expected_payable = lmt_tax_incl - lmt_prepaid + lmt_rounding
        if expected_payable != lmt_payable:
            issues.append(
                ValidationIssue(
                    rule_id="BR-CO-16",
                    severity=Severity.ERROR,
                    xpath="/Invoice/cac:LegalMonetaryTotal/cbc:PayableAmount",
                    message="PayableAmount does not equal TaxInclusiveAmount - PrepaidAmount + PayableRoundingAmount.",
                    expected=str(expected_payable),
                    actual=str(lmt_payable),
                    suggestion=f"Update LegalMonetaryTotal/cbc:PayableAmount to {expected_payable}.",
                )
            )
    elif lmt_payable is None:
        issues.append(
            ValidationIssue(
                rule_id="BR-15",
                severity=Severity.ERROR,
                xpath="/Invoice/cac:LegalMonetaryTotal/cbc:PayableAmount",
                message="Missing or non-numeric LegalMonetaryTotal/PayableAmount.",
                expected="Decimal monetary amount",
                actual="<missing>",
                suggestion="Provide <cbc:PayableAmount> inside cac:LegalMonetaryTotal.",
            )
        )


def validate_xml_string(xml_text: str) -> list[ValidationIssue]:
    """Validate a UBL 2.1 / PEPPOL BIS Billing 3.0 XML string.

    Raises:
        xml.etree.ElementTree.ParseError: If the XML is syntactically malformed.
    """
    root = ET.fromstring(xml_text)
    issues: list[ValidationIssue] = []

    ns, local = _split_tag(root.tag)
    if local != "Invoice":
        issues.append(
            ValidationIssue(
                rule_id="UBL-ROOT-001",
                severity=Severity.ERROR,
                xpath="/",
                message="Root element must be UBL Invoice.",
                expected=f"{{{UBL_INVOICE_NS}}}Invoice",
                actual=root.tag,
                suggestion="Ensure the root element is <Invoice xmlns=\"urn:oasis:names:specification:ubl:schema:xsd:Invoice-2\">.",
            )
        )
        return issues

    if ns != UBL_INVOICE_NS:
        issues.append(
            ValidationIssue(
                rule_id="UBL-NS-001",
                severity=Severity.ERROR,
                xpath="/Invoice",
                message="Invalid UBL 2.1 Invoice root namespace.",
                expected=UBL_INVOICE_NS,
                actual=ns or "<none>",
                suggestion=f"Set xmlns=\"{UBL_INVOICE_NS}\" on the root <Invoice> element.",
            )
        )

    # Mandatory PEPPOL BIS 3.0 header fields
    cust_id = _check_required_text(
        root,
        "cbc:CustomizationID",
        "/Invoice/cbc:CustomizationID",
        "PEPPOL-EN16931-R004",
        "CustomizationID (BT-24)",
        issues,
        f"Set <cbc:CustomizationID>{PEPPOL_BIS3_CUSTOMIZATION_ID}</cbc:CustomizationID>.",
    )
    if cust_id is not None and cust_id != PEPPOL_BIS3_CUSTOMIZATION_ID:
        issues.append(
            ValidationIssue(
                rule_id="PEPPOL-EN16931-R004-SPEC",
                severity=Severity.WARNING,
                xpath="/Invoice/cbc:CustomizationID",
                message="CustomizationID does not match standard PEPPOL BIS Billing 3.0 URN.",
                expected=PEPPOL_BIS3_CUSTOMIZATION_ID,
                actual=cust_id,
                suggestion="Verify whether a custom CIUS/extension is intended.",
            )
        )

    _check_required_text(
        root,
        "cbc:ProfileID",
        "/Invoice/cbc:ProfileID",
        "PEPPOL-BIS-BT23",
        "ProfileID (BT-23)",
        issues,
        "Set <cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>.",
    )
    _check_required_text(
        root,
        "cbc:ID",
        "/Invoice/cbc:ID",
        "BR-02",
        "Invoice number (BT-1)",
        issues,
        "Provide a non-empty invoice identifier in <cbc:ID>.",
    )

    issue_date = _check_required_text(
        root,
        "cbc:IssueDate",
        "/Invoice/cbc:IssueDate",
        "BR-03",
        "Invoice issue date (BT-2)",
        issues,
        "Provide an ISO 8601 date (YYYY-MM-DD) in <cbc:IssueDate>.",
    )
    if issue_date is not None:
        if not ISO_DATE_RE.match(issue_date):
            issues.append(
                ValidationIssue(
                    rule_id="BR-03-FORMAT",
                    severity=Severity.ERROR,
                    xpath="/Invoice/cbc:IssueDate",
                    message="IssueDate must follow ISO 8601 YYYY-MM-DD format.",
                    expected="YYYY-MM-DD",
                    actual=issue_date,
                    suggestion="Format <cbc:IssueDate> as YYYY-MM-DD (e.g., 2026-11-20).",
                )
            )
        else:
            try:
                datetime.date.fromisoformat(issue_date)
            except ValueError:
                issues.append(
                    ValidationIssue(
                        rule_id="BR-03-DATE",
                        severity=Severity.ERROR,
                        xpath="/Invoice/cbc:IssueDate",
                        message="IssueDate is not a valid calendar date.",
                        expected="Valid YYYY-MM-DD calendar date",
                        actual=issue_date,
                        suggestion="Fix the invalid month or day in <cbc:IssueDate>.",
                    )
                )

    type_code = _check_required_text(
        root,
        "cbc:InvoiceTypeCode",
        "/Invoice/cbc:InvoiceTypeCode",
        "BR-04",
        "Invoice type code (BT-3)",
        issues,
        "Provide UNTDID 1001 code (e.g., 380 for Commercial Invoice) in <cbc:InvoiceTypeCode>.",
    )
    if type_code is not None and type_code not in VALID_INVOICE_TYPE_CODES:
        issues.append(
            ValidationIssue(
                rule_id="PEPPOL-EN16931-CL001",
                severity=Severity.WARNING,
                xpath="/Invoice/cbc:InvoiceTypeCode",
                message="InvoiceTypeCode is outside the standard PEPPOL BIS 3.0 invoice code subset.",
                expected=", ".join(sorted(VALID_INVOICE_TYPE_CODES)),
                actual=type_code,
                suggestion="Confirm the UNTDID 1001 type code (380 is standard commercial invoice).",
            )
        )

    doc_currency = _check_required_text(
        root,
        "cbc:DocumentCurrencyCode",
        "/Invoice/cbc:DocumentCurrencyCode",
        "BR-05",
        "Document currency code (BT-5)",
        issues,
        "Provide an ISO 4217 3-letter currency code (e.g., EUR) in <cbc:DocumentCurrencyCode>.",
    )
    if doc_currency is not None and not ISO_CURRENCY_RE.match(doc_currency):
        issues.append(
            ValidationIssue(
                rule_id="BR-05-FORMAT",
                severity=Severity.ERROR,
                xpath="/Invoice/cbc:DocumentCurrencyCode",
                message="DocumentCurrencyCode must be a 3-letter uppercase ISO 4217 code.",
                expected="3 uppercase letters (e.g., EUR, USD, GBP)",
                actual=doc_currency,
                suggestion="Use uppercase ISO 4217 code in <cbc:DocumentCurrencyCode>.",
            )
        )

    # Supplier & Customer EndpointID + @schemeID
    _check_endpoint(root, "AccountingSupplierParty", "Supplier", "PEPPOL-EN16931-R020", issues)
    _check_endpoint(root, "AccountingCustomerParty", "Customer", "PEPPOL-EN16931-R010", issues)

    # At least one InvoiceLine
    lines = root.findall("cac:InvoiceLine", NS)
    if not lines:
        issues.append(
            ValidationIssue(
                rule_id="BR-16",
                severity=Severity.ERROR,
                xpath="/Invoice/cac:InvoiceLine",
                message="An Invoice must contain at least one cac:InvoiceLine.",
                expected=">= 1 cac:InvoiceLine",
                actual="0",
                suggestion="Add at least one <cac:InvoiceLine> element.",
            )
        )

    _check_currency_consistency(root, doc_currency, issues)
    _check_arithmetic(root, issues)

    return issues


def validate_file(path: Path) -> list[ValidationIssue]:
    """Read and validate a UBL 2.1 XML file from disk."""
    content = path.read_text(encoding="utf-8")
    return validate_xml_string(content)
