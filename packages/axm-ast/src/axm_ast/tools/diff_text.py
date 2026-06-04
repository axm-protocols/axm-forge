"""Text renderer for ``ast_diff`` output.

Renders the :func:`structural_diff` payload as a compact changelog,
grouped by file (``## {file}``) with ``+`` added / ``-`` removed /
``~`` changed lines, mirroring the header/glyph conventions of the
sibling ``*_text`` renderers.

Every change is listed; modified symbols carry their before → after
signatures. No change is masked. Compaction is lossless: the file is
hoisted into a section header and the per-symbol ``kind``/``name`` is
carried by the signature itself (``def name(...)`` / ``class Name(...)``),
so the JSON key/quote/escape overhead is the only thing dropped.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TypedDict, cast

__all__ = ["render_diff_text"]


class _SymbolEntry(TypedDict, total=False):
    name: str
    kind: str
    file: str
    signature: str | None


class _ModifiedSymbol(TypedDict, total=False):
    name: str
    kind: str
    file: str
    old_signature: str | None
    new_signature: str | None


class _Summary(TypedDict, total=False):
    added: int
    removed: int
    modified: int


class _DiffData(TypedDict, total=False):
    added: list[_SymbolEntry]
    removed: list[_SymbolEntry]
    modified: list[_ModifiedSymbol]
    summary: _Summary


@dataclass
class _FileBucket:
    added: list[_SymbolEntry] = field(default_factory=list)
    removed: list[_SymbolEntry] = field(default_factory=list)
    modified: list[_ModifiedSymbol] = field(default_factory=list)


def render_diff_text(data: dict[str, object]) -> str:
    """Render a structural diff payload as a compact changelog.

    Args:
        data: Payload from :func:`structural_diff`.

    Returns:
        Changelog text grouped by file: ``+`` added, ``-`` removed,
        ``~`` changed (with before → after signatures).
    """
    typed = cast("_DiffData", data)
    added = typed.get("added") or []
    removed = typed.get("removed") or []
    modified = typed.get("modified") or []
    summary = typed.get("summary") or {}
    n_add = summary.get("added", len(added))
    n_rem = summary.get("removed", len(removed))
    n_mod = summary.get("modified", len(modified))

    lines: list[str] = [f"ast_diff | +{n_add} -{n_rem} ~{n_mod}"]
    for file_name, bucket in _group_by_file(added, removed, modified):
        lines.append(f"## {file_name}")
        lines.extend(f"+ {_symbol_sig(s)}" for s in bucket.added)
        lines.extend(f"- {_symbol_sig(s)}" for s in bucket.removed)
        lines.extend(_render_modified(s) for s in bucket.modified)
    return "\n".join(lines)


def _group_by_file(
    added: list[_SymbolEntry],
    removed: list[_SymbolEntry],
    modified: list[_ModifiedSymbol],
) -> list[tuple[str, _FileBucket]]:
    """Bucket every change by file, preserving the upstream sort order."""
    buckets: dict[str, _FileBucket] = defaultdict(_FileBucket)
    for a in added:
        buckets[a.get("file", "?")].added.append(a)
    for r in removed:
        buckets[r.get("file", "?")].removed.append(r)
    for m in modified:
        buckets[m.get("file", "?")].modified.append(m)
    return sorted(buckets.items(), key=lambda kv: kv[0])


def _symbol_sig(entry: _SymbolEntry) -> str:
    """Signature line for an added/removed symbol; falls back to name."""
    sig = entry.get("signature")
    if sig:
        return sig
    kind = entry.get("kind", "?")
    return f"{kind} {entry.get('name', '?')}"


def _render_modified(entry: _ModifiedSymbol) -> str:
    """Single ``~`` line with before → after signatures."""
    name = entry.get("name", "?")
    old = entry.get("old_signature") or "∅"
    new = entry.get("new_signature") or "∅"
    return f"~ {name}: {old} → {new}"
