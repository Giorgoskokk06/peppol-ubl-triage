# peppol-ubl-triage

Zero-dependency Python CLI for diagnosing broken **OASIS UBL 2.1** and **PEPPOL BIS Billing 3.0 (EN 16931)** XML invoices, diffing XML/JSON integration payloads, and generating copy-pasteable Markdown or JSON triage reports.

Runs on Python 3.11+ using only the standard library (`xml.etree.ElementTree`, `decimal`, `json`, `argparse`).

## Install

```bash
git clone https://github.com/Giorgoskokk06/peppol-ubl-triage.git
cd peppol-ubl-triage
pip install -e .
```

To run the test suite (15 tests):

```bash
pip install -e ".[dev]"
pytest -v
```

## Usage

Validate an invoice against UBL 2.1 / PEPPOL BIS 3.0 rules:

```bash
peppol-triage validate examples/invoice_valid_ubl21.xml
peppol-triage validate examples/invoice_broken_totals.xml --format json
```

Diff two XML or JSON payloads while ignoring formatting and key-order noise:

```bash
peppol-triage diff examples/invoice_v1.json examples/invoice_v2_drift.json
```

Run validation and reference diff together and write a Markdown report for an issue tracker:

```bash
peppol-triage triage examples/invoice_broken_totals.xml \
  --reference examples/invoice_valid_ubl21.xml \
  --format md \
  --out triage_report.md
```

### Example output

Running `peppol-triage diff examples/invoice_v1.json examples/invoice_v2_drift.json`:

```markdown
# PEPPOL / UBL Triage Report

- **Target:** `examples/invoice_v2_drift.json`
- **Reference:** `examples/invoice_v1.json`
- **Status:** `DIFF_DETECTED`
- **Summary:** 0 error(s), 0 warning(s), 0 info, 4 diff(s)

## Semantic Contract Diff

| Change | Path | Before | After |
| --- | --- | --- | --- |
| **VALUE_CHANGED** | `$.currency` | `EUR` | `USD` |
| **REMOVED** | `$.customer.schemeId` | `9930` | — |
| **TYPE_CHANGED** | `$.lines[0].lineId` | `1` | `1` |
| **ADDED** | `$.totals.roundingAmount` | — | `0.00` |
```

Running `peppol-triage validate examples/invoice_broken_totals.xml` flags all 6 errors in the sample payload (`PEPPOL-EN16931-R010-SCHEME`, `PEPPOL-CURR-001`, `BR-CO-10`, `BR-CO-13`, `BR-CO-15`, `BR-CO-16`) with exact XPaths, expected vs. actual `Decimal` values, and suggested fixes.

## Checks implemented

| Category | Rule IDs | What it catches |
| :--- | :--- | :--- |
| Mandatory header fields | `UBL-CR-001` .. `UBL-CR-006` | Missing `CustomizationID`, `ProfileID`, `ID`, ISO 8601 `IssueDate`, `InvoiceTypeCode`, or ISO 4217 `DocumentCurrencyCode` |
| Party endpoints | `PEPPOL-EN16931-R010/-SCHEME`, `R020/-SCHEME` | Missing supplier/customer `EndpointID` or `@schemeID` |
| Currency consistency | `PEPPOL-CURR-001` | Line or total `@currencyID` drifting from `DocumentCurrencyCode` |
| Exact `Decimal` totals | `BR-CO-10`, `BR-CO-13`, `BR-CO-14`, `BR-CO-15`, `BR-CO-16` | Line sum, allowance/charge, tax subtotal, tax-inclusive, and payable amount mismatches |
| Semantic diff | `ADDED`, `REMOVED`, `TYPE_CHANGED`, `VALUE_CHANGED` | Structural and type drift (including `int` vs. `str` and `bool` vs. `int`) across XML or JSON payloads |

## Exit codes

- `0` — Valid invoice or no semantic differences found
- `1` — One or more validation `ERROR` findings or semantic differences detected
- `2` — Missing file, malformed XML/JSON, or mismatched file formats

## Package structure

```text
src/peppol_triage/
  models.py      # Dataclasses and JSON serialization
  validator.py   # UBL 2.1 / PEPPOL BIS 3.0 header, endpoint, currency, and Decimal rules
  differ.py      # Canonical XML (XPath) and JSON (JSONPath) differ
  reporter.py    # Markdown and JSON report renderers
  cli.py         # argparse entrypoint (validate, diff, triage)
examples/        # Valid/broken UBL 2.1 XML and v1/v2 JSON sample payloads
tests/           # 15 pytest tests covering validation, diffing, and CLI exit codes
```

## License

[MIT](LICENSE)
