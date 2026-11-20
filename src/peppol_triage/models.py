"""Data models for UBL validation issues, semantic diffs, and triage reports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Severity level of a validation finding."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class DiffKind(str, Enum):
    """Classification of a semantic difference between two payloads."""

    ADDED = "ADDED"
    REMOVED = "REMOVED"
    TYPE_CHANGED = "TYPE_CHANGED"
    VALUE_CHANGED = "VALUE_CHANGED"


@dataclass(slots=True)
class ValidationIssue:
    """A single structural or arithmetic violation in a UBL 2.1 / PEPPOL BIS 3.0 document."""

    rule_id: str
    severity: Severity
    xpath: str
    message: str
    expected: str | None = None
    actual: str | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the issue to a JSON-compatible dictionary."""
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass(slots=True)
class DiffEntry:
    """A single canonical difference between a reference and target payload."""

    path: str
    kind: DiffKind
    before: Any = None
    after: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the diff entry to a JSON-compatible dictionary."""
        data = asdict(self)
        data["kind"] = self.kind.value
        return data


@dataclass(slots=True)
class TriageReport:
    """Combined validation and diff report ready for Markdown or JSON rendering."""

    target: str
    reference: str | None = None
    issues: list[ValidationIssue] = field(default_factory=list)
    diffs: list[DiffEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == Severity.INFO)

    @property
    def valid(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full triage report to a JSON-compatible dictionary."""
        return {
            "target": self.target,
            "reference": self.reference,
            "valid": self.valid,
            "summary": {
                "errors": self.error_count,
                "warnings": self.warning_count,
                "info": self.info_count,
                "diffs": len(self.diffs),
            },
            "issues": [issue.to_dict() for issue in self.issues],
            "diffs": [diff.to_dict() for diff in self.diffs],
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Render the triage report as formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
