"""Markdown (Jira/GitHub-ready) and JSON report renderers."""

from __future__ import annotations

from typing import Any

from peppol_triage.models import TriageReport


def _escape_md_cell(value: Any) -> str:
    if value is None:
        return "—"
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return f"`{text}`" if text else "—"


def render_markdown(report: TriageReport) -> str:
    """Render a TriageReport as copy-pasteable Jira/GitHub Markdown."""
    status_label = "PASS" if report.valid and not report.diffs else (
        "FAIL" if not report.valid else "DIFF_DETECTED"
    )
    lines: list[str] = [
        "# PEPPOL / UBL Triage Report",
        "",
        f"- **Target:** `{report.target}`",
    ]
    if report.reference:
        lines.append(f"- **Reference:** `{report.reference}`")

    lines.extend(
        [
            f"- **Status:** `{status_label}`",
            (
                f"- **Summary:** {report.error_count} error(s), "
                f"{report.warning_count} warning(s), "
                f"{report.info_count} info, "
                f"{len(report.diffs)} diff(s)"
            ),
            "",
        ]
    )

    if report.issues:
        lines.extend(
            [
                "## Validation Findings",
                "",
                "| Severity | Rule ID | XPath | Message | Expected | Actual | Suggested Fix |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for issue in report.issues:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"**{issue.severity.value}**",
                        _escape_md_cell(issue.rule_id),
                        _escape_md_cell(issue.xpath),
                        issue.message.replace("|", "\\|"),
                        _escape_md_cell(issue.expected),
                        _escape_md_cell(issue.actual),
                        (issue.suggestion or "—").replace("|", "\\|"),
                    ]
                )
                + " |"
            )
        lines.append("")
    elif report.target and report.metadata.get("mode") != "diff":
        lines.extend(
            [
                "## Validation Findings",
                "",
                "No UBL 2.1 / PEPPOL BIS 3.0 validation issues detected.",
                "",
            ]
        )

    if report.diffs:
        lines.extend(
            [
                "## Semantic Contract Diff",
                "",
                "| Change | Path | Before | After |",
                "| --- | --- | --- | --- |",
            ]
        )
        for diff in report.diffs:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"**{diff.kind.value}**",
                        _escape_md_cell(diff.path),
                        _escape_md_cell(diff.before),
                        _escape_md_cell(diff.after),
                    ]
                )
                + " |"
            )
        lines.append("")

    return "\n".join(lines)


def render_json(report: TriageReport) -> str:
    """Render a TriageReport as formatted JSON."""
    return report.to_json(indent=2)
