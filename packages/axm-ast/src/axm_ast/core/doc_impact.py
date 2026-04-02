"""Doc impact analysis — doc refs, undocumented symbols, stale signatures."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

__all__ = [
    "analyze_doc_impact",
    "find_doc_refs",
    "find_stale_signatures",
    "find_undocumented",
]

_CODE_FENCE_RE = re.compile(r"^```(?:python|py)?\s*$", re.IGNORECASE)
_CODE_FENCE_END_RE = re.compile(r"^```\s*$")
_DEF_RE = re.compile(r"^\s*(def|class)\s+(\w+)")


# ─── Internal helpers ────────────────────────────────────────────────────────


def _collect_doc_files(root: Path) -> list[Path]:
    """Collect README and docs/**/*.md files."""
    files: list[Path] = []
    for name in ("README.md", "README.rst", "readme.md"):
        p = root / name
        if p.is_file():
            files.append(p)
            break
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        files.extend(sorted(docs_dir.rglob("*.md")))
    return files


def _search_symbol_in_file(
    path: Path,
    symbol: str,
    root: Path,
) -> list[dict[str, Any]]:
    """Search for symbol mentions in a documentation file.

    Only matches backtick-wrapped references (`` `symbol` ``)
    or markdown headings containing the symbol name.
    """
    refs: list[dict[str, Any]] = []
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return refs
    esc = re.escape(symbol)
    backtick_pat = re.compile(rf"`[^`]*{esc}[^`]*`")
    heading_pat = re.compile(rf"^#+\s+.*{esc}", re.IGNORECASE)
    for lineno, line in enumerate(content.splitlines(), start=1):
        if backtick_pat.search(line) or heading_pat.search(line):
            rel = str(path.relative_to(root))
            refs.append({"file": rel, "line": lineno})
    return refs


def _extract_ast_signatures(root: Path) -> dict[str, str]:
    """Extract function/class signatures from all .py files under src/."""
    sigs: dict[str, str] = {}
    src_dir = root / "src"
    search_dirs = [src_dir] if src_dir.is_dir() else [root]
    for search_dir in search_dirs:
        for py_file in search_dir.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    sig = ast.get_source_segment(source, node)
                    if sig:
                        first_line = sig.split("\n")[0]
                        # Remove trailing colon for comparison
                        sigs[node.name] = first_line.rstrip().rstrip(":")
                elif isinstance(node, ast.ClassDef):
                    sigs[node.name] = f"class {node.name}"
    return sigs


def _match_signature_line(
    line: str,
    lineno: int,
    symbols: set[str],
    path: Path,
    root: Path,
) -> dict[str, Any] | None:
    """Return a signature dict if *line* matches a tracked symbol."""
    m = _DEF_RE.match(line)
    if not m or m.group(2) not in symbols:
        return None
    sig = line.strip().rstrip(":").rstrip()
    rel = str(path.relative_to(root))
    return {"symbol": m.group(2), "file": rel, "doc_sig": sig, "line": lineno}


def _extract_doc_signatures(
    path: Path,
    symbols: set[str],
    root: Path,
) -> list[dict[str, Any]]:
    """Extract def/class signatures from code blocks in a doc file."""
    results: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return results
    in_code_block = False
    for lineno, line in enumerate(lines, 1):
        if not in_code_block and _CODE_FENCE_RE.match(line):
            in_code_block = True
            continue
        if in_code_block and _CODE_FENCE_END_RE.match(line):
            in_code_block = False
            continue
        if in_code_block:
            hit = _match_signature_line(line, lineno, symbols, path, root)
            if hit:
                results.append(hit)
    return results


# ─── Public API ──────────────────────────────────────────────────────────────


def find_doc_refs(
    root: Path,
    symbols: list[str],
) -> dict[str, list[dict[str, Any]]]:
    """Find documentation references for given symbols.

    Args:
        root: Project root directory.
        symbols: Symbol names to search for in docs.

    Returns:
        Dict mapping symbol name to list of references
        (each with ``file`` and ``line`` keys).
    """
    doc_files = _collect_doc_files(root)
    refs: dict[str, list[dict[str, Any]]] = {s: [] for s in symbols}
    for sym in symbols:
        for doc_file in doc_files:
            hits = _search_symbol_in_file(doc_file, sym, root)
            refs[sym].extend(hits)
    return refs


def find_undocumented(
    doc_refs: dict[str, list[dict[str, Any]]],
) -> list[str]:
    """Return symbols that have no documentation references.

    Args:
        doc_refs: Output of ``find_doc_refs``.

    Returns:
        List of symbol names with empty references.
    """
    return [sym for sym, refs in doc_refs.items() if not refs]


def find_stale_signatures(
    root: Path,
    symbols: list[str],
) -> list[dict[str, Any]]:
    """Detect stale code signatures in documentation.

    Compares ``def`` / ``class`` signatures in doc code blocks
    against actual AST signatures.

    Args:
        root: Project root directory.
        symbols: Symbol names to check.

    Returns:
        List of dicts with ``symbol``, ``file``, ``doc_sig``,
        ``actual_sig``, and ``line`` keys.
    """
    ast_sigs = _extract_ast_signatures(root)
    doc_files = _collect_doc_files(root)
    sym_set = set(symbols)
    stale: list[dict[str, Any]] = []
    for doc_file in doc_files:
        doc_sigs = _extract_doc_signatures(doc_file, sym_set, root)
        for entry in doc_sigs:
            sym_name = entry["symbol"]
            if sym_name in ast_sigs:
                actual = ast_sigs[sym_name]
                doc_sig = entry["doc_sig"]
                # Normalize for comparison: strip whitespace
                if doc_sig.strip() != actual.strip():
                    entry["actual_sig"] = actual
                    stale.append(entry)
    return stale


def analyze_doc_impact(
    root: Path,
    symbols: list[str],
) -> dict[str, Any]:
    """Full doc impact analysis for a set of symbols.

    Combines doc refs, undocumented detection, and stale
    signature detection.

    Args:
        root: Project root directory.
        symbols: Symbol names to analyze.

    Returns:
        Dict with ``doc_refs``, ``undocumented``, ``stale_signatures``.
    """
    refs = find_doc_refs(root, symbols)
    return {
        "doc_refs": refs,
        "undocumented": find_undocumented(refs),
        "stale_signatures": find_stale_signatures(root, symbols),
    }
