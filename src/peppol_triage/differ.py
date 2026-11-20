"""Semantic canonical diff for XML and JSON integration payloads."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from peppol_triage.models import DiffEntry, DiffKind
from peppol_triage.validator import CAC_NS, CBC_NS, UBL_INVOICE_NS


def _normalize_text(text: str | None) -> str:
    if text is None:
        return ""
    return " ".join(text.split())


def _canonical_xml_tag(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        ns, local = tag[1:].split("}", 1)
        if ns == UBL_INVOICE_NS:
            return local
        if ns == CBC_NS:
            return f"cbc:{local}"
        if ns == CAC_NS:
            return f"cac:{local}"
        return f"{{{ns}}}{local}"
    return tag


def diff_json(before: Any, after: Any, path: str = "$") -> list[DiffEntry]:
    """Compute a semantic diff between two JSON-compatible Python structures."""
    entries: list[DiffEntry] = []

    if type(before) is not type(after):
        # Allow int vs float? In JSON contract diffing, int->float or str->int is TYPE_CHANGED.
        entries.append(
            DiffEntry(
                path=path,
                kind=DiffKind.TYPE_CHANGED,
                before=before,
                after=after,
            )
        )
        return entries

    if isinstance(before, dict):
        all_keys = sorted(set(before.keys()) | set(after.keys()))
        for key in all_keys:
            child_path = f"{path}.{key}"
            if key not in before:
                entries.append(
                    DiffEntry(
                        path=child_path,
                        kind=DiffKind.ADDED,
                        before=None,
                        after=after[key],
                    )
                )
            elif key not in after:
                entries.append(
                    DiffEntry(
                        path=child_path,
                        kind=DiffKind.REMOVED,
                        before=before[key],
                        after=None,
                    )
                )
            else:
                entries.extend(diff_json(before[key], after[key], child_path))
        return entries

    if isinstance(before, list):
        shared = min(len(before), len(after))
        for idx in range(shared):
            entries.extend(diff_json(before[idx], after[idx], f"{path}[{idx}]"))
        for idx in range(shared, len(after)):
            entries.append(
                DiffEntry(
                    path=f"{path}[{idx}]",
                    kind=DiffKind.ADDED,
                    before=None,
                    after=after[idx],
                )
            )
        for idx in range(shared, len(before)):
            entries.append(
                DiffEntry(
                    path=f"{path}[{idx}]",
                    kind=DiffKind.REMOVED,
                    before=before[idx],
                    after=None,
                )
            )
        return entries

    if before != after:
        entries.append(
            DiffEntry(
                path=path,
                kind=DiffKind.VALUE_CHANGED,
                before=before,
                after=after,
            )
        )

    return entries


def _group_children(element: ET.Element) -> dict[str, list[ET.Element]]:
    grouped: dict[str, list[ET.Element]] = {}
    for child in element:
        label = _canonical_xml_tag(child.tag)
        grouped.setdefault(label, []).append(child)
    return grouped


def _element_summary(element: ET.Element) -> str:
    text = _normalize_text(element.text)
    if text:
        return text
    if element.attrib:
        attrs = " ".join(f'{k}="{v}"' for k, v in sorted(element.attrib.items()))
        return f"<{_canonical_xml_tag(element.tag)} {attrs}>"
    return f"<{_canonical_xml_tag(element.tag)}>"


def _diff_xml_elements(
    before_el: ET.Element,
    after_el: ET.Element,
    path: str,
    entries: list[DiffEntry],
) -> None:
    # Compare attributes
    all_attrs = sorted(set(before_el.attrib.keys()) | set(after_el.attrib.keys()))
    for attr in all_attrs:
        attr_path = f"{path}/@{attr}"
        if attr not in before_el.attrib:
            entries.append(
                DiffEntry(
                    path=attr_path,
                    kind=DiffKind.ADDED,
                    before=None,
                    after=after_el.attrib[attr],
                )
            )
        elif attr not in after_el.attrib:
            entries.append(
                DiffEntry(
                    path=attr_path,
                    kind=DiffKind.REMOVED,
                    before=before_el.attrib[attr],
                    after=None,
                )
            )
        elif before_el.attrib[attr] != after_el.attrib[attr]:
            entries.append(
                DiffEntry(
                    path=attr_path,
                    kind=DiffKind.VALUE_CHANGED,
                    before=before_el.attrib[attr],
                    after=after_el.attrib[attr],
                )
            )

    # Compare normalized text
    before_text = _normalize_text(before_el.text)
    after_text = _normalize_text(after_el.text)
    if before_text != after_text:
        entries.append(
            DiffEntry(
                path=path,
                kind=DiffKind.VALUE_CHANGED,
                before=before_text or None,
                after=after_text or None,
            )
        )

    # Compare children grouped by canonical tag
    before_groups = _group_children(before_el)
    after_groups = _group_children(after_el)
    all_tags = sorted(set(before_groups.keys()) | set(after_groups.keys()))

    for tag in all_tags:
        b_list = before_groups.get(tag, [])
        a_list = after_groups.get(tag, [])
        max_count = max(len(b_list), len(a_list))
        shared = min(len(b_list), len(a_list))

        for idx in range(shared):
            suffix = f"[{idx + 1}]" if max_count > 1 else ""
            _diff_xml_elements(b_list[idx], a_list[idx], f"{path}/{tag}{suffix}", entries)

        for idx in range(shared, len(a_list)):
            suffix = f"[{idx + 1}]" if max_count > 1 else ""
            entries.append(
                DiffEntry(
                    path=f"{path}/{tag}{suffix}",
                    kind=DiffKind.ADDED,
                    before=None,
                    after=_element_summary(a_list[idx]),
                )
            )

        for idx in range(shared, len(b_list)):
            suffix = f"[{idx + 1}]" if max_count > 1 else ""
            entries.append(
                DiffEntry(
                    path=f"{path}/{tag}{suffix}",
                    kind=DiffKind.REMOVED,
                    before=_element_summary(b_list[idx]),
                    after=None,
                )
            )


def diff_xml(before_xml: str, after_xml: str) -> list[DiffEntry]:
    """Compute a semantic canonical diff between two XML strings."""
    before_root = ET.fromstring(before_xml)
    after_root = ET.fromstring(after_xml)

    before_tag = _canonical_xml_tag(before_root.tag)
    after_tag = _canonical_xml_tag(after_root.tag)
    if before_tag != after_tag:
        return [
            DiffEntry(
                path="/",
                kind=DiffKind.VALUE_CHANGED,
                before=before_tag,
                after=after_tag,
            )
        ]

    entries: list[DiffEntry] = []
    _diff_xml_elements(before_root, after_root, f"/{before_tag}", entries)
    return entries


def _detect_format(path: Path, content: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".xml":
        return "xml"
    stripped = content.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    if stripped.startswith("<"):
        return "xml"
    raise ValueError(f"Unable to detect payload format (XML or JSON) for: {path}")


def diff_files(before_path: Path, after_path: Path) -> list[DiffEntry]:
    """Read two XML or JSON files and return their semantic diff."""
    before_raw = before_path.read_text(encoding="utf-8")
    after_raw = after_path.read_text(encoding="utf-8")

    fmt_before = _detect_format(before_path, before_raw)
    fmt_after = _detect_format(after_path, after_raw)
    if fmt_before != fmt_after:
        raise ValueError(
            f"Cannot diff mismatched payload formats: {before_path} ({fmt_before}) vs {after_path} ({fmt_after})."
        )

    if fmt_before == "json":
        return diff_json(json.loads(before_raw), json.loads(after_raw))
    return diff_xml(before_raw, after_raw)
