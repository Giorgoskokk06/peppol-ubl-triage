# peppol-ubl-triage

> **Diagnose broken UBL 2.1 / PEPPOL BIS Billing 3.0 e-invoices in seconds:** deterministic structural + `Decimal` arithmetic validation, semantic XML/JSON contract diffing, and one-command Jira/GitHub bug-repro reports.

Built purely on public **OASIS UBL 2.1** and **EU PEPPOL BIS Billing 3.0 (EN 16931)** open standards using only the Python 3.11+ standard library (zero runtime dependencies).

---

## Why This Exists

When an ERP or middleware integration fails PEPPOL / UBL validation, engineers spend too long reading raw XML payloads to find:
- `0.01` rounding or total mismatches (`BR-CO-10`, `BR-CO-13`, `BR-CO-14`, `BR-CO-15`, `BR-CO-16`)
- missing `EndpointID` or `@schemeID` attributes (`PEPPOL-EN16931-R010` / `-SCHEME`, `PEPPOL-EN16931-R020` / `-SCHEME`)
- silent currency drift on a single line item (`PEPPOL-CURR-001`)
- schema/type drift between v1 and v2 JSON or XML integration contracts

`peppol-ubl-triage` turns raw payloads into a deterministic, copy-pasteable Markdown or JSON triage report in one command.

---

## Installation

```bash
pip install -e .
```

For development and running tests:

```bash
pip install -e ".[dev]"
pytest -v
```

---

## CLI Usage

### 1. Validate a UBL 2.1 / PEPPOL BIS 3.0 XML invoice

```bash
peppol-triage validate examples/invoice_valid_ubl21.xml
peppol-triage validate examples/invoice_broken_totals.xml --format json
```

### 2. Semantic Diff (XML or JSON)

Ignores whitespace and JSON key-order noise; highlights exact XPath / JSONPath `ADDED`, `REMOVED`, `TYPE_CHANGED`, and `VALUE_CHANGED` entries:

```bash
peppol-triage diff examples/invoice_v1.json examples/invoice_v2_drift.json
```

### 3. Full Triage (Validate + Reference Diff -> Jira/GitHub Markdown)

```bash
peppol-triage triage examples/invoice_broken_totals.xml \
  --reference examples/invoice_valid_ubl21.xml \
  --format md \
  --out triage_report.md
```

### Exit Codes

- `0` — Clean (valid UBL XML / no semantic diff)
- `1` — Validation `ERROR`(s) found or semantic diff detected
- `2` — I/O, XML/JSON parse, or format mismatch error

---

## Sample Output

```markdown
# PEPPOL / UBL Triage Report

- **Target:** `examples/invoice_broken_totals.xml`
- **Reference:** `examples/invoice_valid_ubl21.xml`
- **Status:** `FAIL`
- **Summary:** 6 error(s), 0 warning(s), 0 info, 5 diff(s)

## Validation Findings

| Severity | Rule ID | XPath | Message | Expected | Actual | Suggested Fix |
| --- | --- | --- | --- | --- | --- | --- |
| **ERROR** | `PEPPOL-EN16931-R010-SCHEME` | `/Invoice/cac:AccountingCustomerParty/cac:Party/cbc:EndpointID/@schemeID` | Customer EndpointID is missing required @schemeID attribute. | `Valid EAS schemeID (e.g., 0088, 0192, 9930)` | `<missing>` | Add schemeID attribute from the PEPPOL Electronic Address Scheme (EAS) list. |
| **ERROR** | `PEPPOL-CURR-001` | `/Invoice/cac:InvoiceLine[2]/cbc:LineExtensionAmount/@currencyID` | Element currencyID does not match DocumentCurrencyCode. | `EUR` | `USD` | Align @currencyID to 'EUR'. |
| **ERROR** | `BR-CO-10` | `/Invoice/cac:LegalMonetaryTotal/cbc:LineExtensionAmount` | Sum of InvoiceLine/LineExtensionAmount does not equal LegalMonetaryTotal/LineExtensionAmount. | `350.00` | `999.00` | Update LegalMonetaryTotal/cbc:LineExtensionAmount to 350.00. |
```

---

## Architecture

```text
src/peppol_triage/
├── models.py      # Severity, DiffKind, ValidationIssue, DiffEntry, TriageReport
├── validator.py   # OASIS UBL 2.1 / PEPPOL BIS 3.0 structural + Decimal arithmetic rules
├── differ.py      # Canonical semantic XML & JSON differ (XPath / JSONPath)
├── reporter.py    # Jira/GitHub-ready Markdown & JSON report renderers
└── cli.py         # argparse CLI (`validate`, `diff`, `triage`)
```

## License

MIT — see [LICENSE](LICENSE).
