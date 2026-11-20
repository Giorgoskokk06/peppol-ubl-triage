"""Command-line interface for peppol-ubl-triage."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

from peppol_triage.differ import diff_files
from peppol_triage.models import TriageReport
from peppol_triage.reporter import render_json, render_markdown
from peppol_triage.validator import validate_file


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="peppol-triage",
        description=(
            "Diagnose broken UBL 2.1 / PEPPOL BIS Billing 3.0 e-invoices: "
            "deterministic validation, semantic XML/JSON diffing, and Jira-ready triage reports."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = subparsers.add_parser("validate", help="Validate a UBL 2.1 / PEPPOL BIS 3.0 XML file.")
    p_val.add_argument("file", type=Path, help="Path to the UBL XML invoice file.")
    p_val.add_argument("--format", choices=("md", "json"), default="md", help="Output format.")
    p_val.add_argument("--out", type=Path, default=None, help="Optional output file path.")

    # diff
    p_diff = subparsers.add_parser("diff", help="Semantic diff between two XML or JSON payloads.")
    p_diff.add_argument("before", type=Path, help="Baseline/reference XML or JSON file.")
    p_diff.add_argument("after", type=Path, help="Target/drifted XML or JSON file.")
    p_diff.add_argument("--format", choices=("md", "json"), default="md", help="Output format.")
    p_diff.add_argument("--out", type=Path, default=None, help="Optional output file path.")

    # triage
    p_triage = subparsers.add_parser(
        "triage",
        help="Validate a broken UBL XML file and optionally diff against a reference XML.",
    )
    p_triage.add_argument("broken_xml", type=Path, help="Path to the broken UBL XML invoice.")
    p_triage.add_argument(
        "--reference",
        type=Path,
        default=None,
        help="Optional reference valid UBL XML for semantic diffing.",
    )
    p_triage.add_argument("--format", choices=("md", "json"), default="md", help="Output format.")
    p_triage.add_argument("--out", type=Path, default=None, help="Optional output file path.")

    return parser


def _write_output(rendered: str, out_path: Path | None) -> None:
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for peppol-triage CLI.

    Exit codes:
        0: Clean (valid XML / no diff)
        1: Validation errors or semantic diff detected
        2: IO, parse, or format error
    """
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if args.command == "validate":
            issues = validate_file(args.file)
            report = TriageReport(target=str(args.file), issues=issues)
            rendered = render_json(report) if args.format == "json" else render_markdown(report)
            _write_output(rendered, args.out)
            return 0 if report.valid else 1

        if args.command == "diff":
            diffs = diff_files(args.before, args.after)
            report = TriageReport(
                target=str(args.after),
                reference=str(args.before),
                diffs=diffs,
                metadata={"mode": "diff"},
            )
            rendered = render_json(report) if args.format == "json" else render_markdown(report)
            _write_output(rendered, args.out)
            return 0 if not diffs else 1

        if args.command == "triage":
            issues = validate_file(args.broken_xml)
            diffs = (
                diff_files(args.reference, args.broken_xml)
                if args.reference is not None
                else []
            )
            report = TriageReport(
                target=str(args.broken_xml),
                reference=str(args.reference) if args.reference else None,
                issues=issues,
                diffs=diffs,
            )
            rendered = render_json(report) if args.format == "json" else render_markdown(report)
            _write_output(rendered, args.out)
            return 0 if (report.valid and not diffs) else 1

    except (OSError, ET.ParseError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
