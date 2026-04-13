from __future__ import annotations

from typing import Any

__all__ = ["render_doc_impact_text"]


def _header(result: dict[str, Any]) -> str:
    """Build header line with counts."""
    doc_refs = result.get("doc_refs", {})
    undocumented = result.get("undocumented", [])
    stale = result.get("stale_signatures", [])

    n_symbols = len(doc_refs) | len(set(doc_refs) | set(undocumented))
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


def _render_refs(doc_refs: dict[str, list[dict[str, Any]]]) -> str:
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


def _render_stale(stale: list[dict[str, Any]]) -> str:
    """Render stale signatures section."""
    if not stale:
        return ""
    lines: list[str] = []
    for entry in stale:
        lines.append(f"  {entry['symbol']} @ {entry['file']}:{entry['line']}")
        lines.append(f"    doc:    {entry['doc_sig']}")
        lines.append(f"    actual: {entry['actual_sig']}")
    return "stale:\n" + "\n".join(lines)


def render_doc_impact_text(result: dict[str, Any]) -> str:
    """Render doc impact result as compact text."""
    parts = [_header(result)]

    refs_text = _render_refs(result.get("doc_refs", {}))
    if refs_text:
        parts.append(refs_text)

    undocumented = result.get("undocumented", [])
    if undocumented:
        parts.append(f"undocumented: {', '.join(undocumented)}")

    stale_text = _render_stale(result.get("stale_signatures", []))
    if stale_text:
        parts.append(stale_text)

    return "\n\n".join(parts)
