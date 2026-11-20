"""peppol_triage: Deterministic UBL 2.1 / PEPPOL BIS Billing 3.0 triage toolkit."""

from peppol_triage.differ import diff_files, diff_json, diff_xml
from peppol_triage.models import DiffEntry, DiffKind, Severity, TriageReport, ValidationIssue
from peppol_triage.reporter import render_json, render_markdown
from peppol_triage.validator import validate_file, validate_xml_string

__all__ = [
    "DiffEntry",
    "DiffKind",
    "Severity",
    "TriageReport",
    "ValidationIssue",
    "diff_files",
    "diff_json",
    "diff_xml",
    "render_json",
    "render_markdown",
    "validate_file",
    "validate_xml_string",
]

__version__ = "0.1.0"
