from __future__ import annotations

from typing import TypedDict

__all__ = [
    "DocImpactResult",
    "DocRefEntry",
    "StaleSignature",
    "render_doc_impact_text",
]


class DocRefEntry(TypedDict):
    """Single documentation reference for a symbol."""

    file: str
    line: int


class StaleSignature(TypedDict):
    """Stale documentation signature entry."""

    symbol: str
    file: str
    line: int
    doc_sig: str
    actual_sig: str


class DocImpactResult(TypedDict):
    """Result shape returned by ``analyze_doc_impact``."""

    doc_refs: dict[str, list[DocRefEntry]]
    undocumented: list[str]
    stale_signatures: list[StaleSignature]


def _header(result: DocImpactResult) -> str:
    """Build header line with counts."""
    doc_refs = result["doc_refs"]
    undocumented = result["undocumented"]
    stale = result["stale_signatures"]

    # Count all unique symbols from doc_refs keys + undocumented
    all_symbols = set(doc_refs) | set(undocumented)
    n_symbols = len(all_symbols)
    n_documented = sum(1 for refs in doc_refs.values() if refs)
    n_undocumented = len(undocumented)
    n_stale = len(stale)

    return (
        f"ast_doc_impact | {n_symbols} symbols"
        f" \u00b7 {n_documented} documented"
        f" \u00b7 {n_undocumented} undocumented"
        f" \u00b7 {n_stale} stale"
    )


def _render_refs(doc_refs: dict[str, list[DocRefEntry]]) -> str:
    """Render refs section grouped by file."""
    lines: list[str] = []
    for symbol, refs in doc_refs.items():
        if not refs:
            continue
        total = len(refs)
        by_file: dict[str, list[int]] = {}
        for ref in refs:
            by_file.setdefault(ref["file"], []).append(ref["line"])
        groups = [
            f"{f}:{','.join(str(ln) for ln in lns)}" for f, lns in by_file.items()
        ]
        lines.append(f"  {symbol} ({total}): {' \u00b7 '.join(groups)}")
    if not lines:
        return ""
    return "refs:\n" + "\n".join(lines)


def _render_stale(stale: list[StaleSignature]) -> str:
    """Render stale signatures section."""
    if not stale:
        return ""
    lines: list[str] = []
    for entry in stale:
        lines.append(f"  {entry['symbol']} @ {entry['file']}:{entry['line']}")
        lines.append(f"    doc:    {entry['doc_sig']}")
        lines.append(f"    actual: {entry['actual_sig']}")
    return "stale:\n" + "\n".join(lines)


def render_doc_impact_text(result: DocImpactResult) -> str:
    """Render doc impact result as compact text."""
    parts = [_header(result)]

    refs_text = _render_refs(result["doc_refs"])
    if refs_text:
        parts.append(refs_text)

    undocumented = result["undocumented"]
    if undocumented:
        parts.append(f"undocumented: {', '.join(undocumented)}")

    stale_text = _render_stale(result["stale_signatures"])
    if stale_text:
        parts.append(stale_text)

    return "\n\n".join(parts)
