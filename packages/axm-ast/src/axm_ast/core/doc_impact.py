"""Doc impact analysis — doc refs, undocumented symbols, stale signatures."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import NotRequired, TypedDict

from axm_ast.doc_policy import is_documentation_required
from axm_ast.models.nodes import ClassInfo, FunctionInfo, ModuleInfo

log = logging.getLogger(__name__)

# A symbol node whose documentation-required status the shared policy can judge.
type DocSymbolNode = FunctionInfo | ClassInfo | ModuleInfo

__all__ = [
    "DocImpactResult",
    "DocRefEntry",
    "StaleSignature",
    "analyze_doc_impact",
    "find_doc_refs",
    "find_stale_signatures",
    "find_undocumented",
]


class DocRefEntry(TypedDict):
    """Single documentation reference (backtick mention or heading hit)."""

    file: str
    line: int


class StaleSignature(TypedDict):
    """Stale signature record extracted from a doc code block.

    ``actual_sig`` is added only after matching against the AST signatures;
    intermediate entries produced by :func:`_match_signature_line` omit it.
    """

    symbol: str
    file: str
    doc_sig: str
    line: int
    actual_sig: NotRequired[str]


class DocImpactResult(TypedDict):
    """Output shape of :func:`analyze_doc_impact`."""

    doc_refs: dict[str, list[DocRefEntry]]
    undocumented: list[str]
    stale_signatures: list[StaleSignature]


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
) -> list[DocRefEntry]:
    """Search for symbol mentions in a documentation file.

    Only matches backtick-wrapped references (`` `symbol` ``)
    or markdown headings containing the symbol name.
    """
    refs: list[DocRefEntry] = []
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


def _node_sig(node: ast.AST, src: str, mod_key: str) -> tuple[str, str] | None:
    """Return ``(qualified_name, signature)`` for a def/class node."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        seg = ast.get_source_segment(src, node)
        if seg:
            first_line = seg.split("\n")[0]
            qualified = f"{mod_key}.{node.name}"
            return qualified, first_line.rstrip().rstrip(":")
        return None
    if isinstance(node, ast.ClassDef):
        qualified = f"{mod_key}.{node.name}"
        if node.bases:
            bases_str = ", ".join(ast.unparse(b) for b in node.bases)
            return qualified, f"class {node.name}({bases_str})"
        return qualified, f"class {node.name}"
    return None


def _extract_ast_signatures(root: Path) -> dict[str, str]:
    """Extract function/class signatures from all ``.py`` files under *root*.

    Walks ``src/`` (or *root* directly when no ``src/`` exists) and builds a
    mapping of ``module.qualified_name`` to the first-line signature string.
    Class entries include base classes when present.

    Args:
        root: Project root directory containing a ``src/`` layout or plain
            Python packages.

    Returns:
        Mapping of fully-qualified symbol names to their signature strings.
    """
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
            module_key = ".".join(py_file.relative_to(search_dir).with_suffix("").parts)
            for node in ast.walk(tree):
                entry = _node_sig(node, source, module_key)
                if entry:
                    sigs[entry[0]] = entry[1]
    return sigs


def _match_signature_line(
    line: str,
    lineno: int,
    symbols: set[str],
    path: Path,
    root: Path,
) -> StaleSignature | None:
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
) -> list[StaleSignature]:
    """Extract def/class signatures from code blocks in a doc file."""
    results: list[StaleSignature] = []
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
) -> dict[str, list[DocRefEntry]]:
    """Find documentation references for given symbols.

    The hit is **purely lexical**: a reference is recorded when the bare
    symbol name appears between backticks or in a Markdown heading of a doc
    file. Nothing else is interpreted — prose outside those two forms, and
    the body of a fenced code block, establish no semantic link.

    The returned entries are pages to read, never a non-regression oracle:
    a stable output does not prove the prose still describes the code.

    Args:
        root: Project root directory.
        symbols: Symbol names to search for in docs.

    Returns:
        Dict mapping symbol name to list of references
        (each with ``file`` and ``line`` keys).
    """
    doc_files = _collect_doc_files(root)
    refs: dict[str, list[DocRefEntry]] = {s: [] for s in symbols}
    for sym in symbols:
        for doc_file in doc_files:
            hits = _search_symbol_in_file(doc_file, sym, root)
            refs[sym].extend(hits)
    return refs


def _index_symbol_nodes(root: Path) -> dict[str, DocSymbolNode]:
    """Map bare symbol names to their parsed axm-ast nodes.

    Uses the canonical axm-ast package extraction (``get_package``) so the
    docstring signal fed to :func:`is_documentation_required` is exactly what
    the tree-sitter parser recorded — no bespoke "has docstring" heuristic is
    introduced here.

    Args:
        root: Project root directory to analyze.

    Returns:
        Mapping of bare name to the first node (function, method, or class)
        seen under that name. Empty when the root cannot be analyzed.
    """
    from axm_ast.core.cache import get_package

    try:
        pkg = get_package(root)
    except ValueError:
        return {}
    index: dict[str, DocSymbolNode] = {}
    for module in pkg.modules:
        for fn in module.functions:
            index.setdefault(fn.name, fn)
        for cls in module.classes:
            index.setdefault(cls.name, cls)
            for method in cls.methods:
                index.setdefault(method.name, method)
    return index


def find_undocumented(
    doc_refs: dict[str, list[DocRefEntry]],
    symbol_nodes: dict[str, DocSymbolNode],
) -> list[str]:
    """Return public, docstring-less symbols absent from the prose docs.

    A symbol is reported only when it has **no** prose documentation reference
    *and* the shared :func:`is_documentation_required` policy considers it a
    real gap — i.e. it is public surface (name not ``_``-prefixed) and carries
    no docstring. Private/dunder symbols and symbols already documented by a
    docstring are never reported; this can only ever *shrink* the prose-missing
    set, never grow it (the output schema is unchanged).

    A symbol absent from ``symbol_nodes`` (unresolvable in the analyzed source)
    keeps the legacy prose-only verdict, so a genuinely missing symbol is never
    silently dropped.

    The prose signal it consumes is **purely lexical**: ``find_doc_refs`` only
    matches the bare name between backticks or in a Markdown heading, and never
    reads the meaning of a fenced code block. A single name-drop of the symbol
    therefore suffices to drop it from this list, without any real prose being
    written. See :func:`analyze_doc_impact` for the canonical caveat.

    Args:
        doc_refs: Output of ``find_doc_refs``.
        symbol_nodes: Bare-name → parsed node index (see
            :func:`_index_symbol_nodes`) supplying the docstring/privacy signal.

    Returns:
        List of symbol names that are documentation-required gaps.
    """
    undocumented: list[str] = []
    for sym, refs in doc_refs.items():
        if refs:
            continue
        node = symbol_nodes.get(sym)
        if node is not None and not is_documentation_required(node):
            continue
        undocumented.append(sym)
    return undocumented


def find_stale_signatures(
    root: Path,
    symbols: list[str] | None = None,
) -> list[StaleSignature]:
    """Detect stale code signatures in documentation.

    Compares ``def`` / ``class`` signatures in doc code blocks
    against actual AST signatures.

    The scope is strictly a fenced code block: a signature written in plain
    prose, in an indented block or in an inline span is never extracted. The
    comparison itself is a lexical string equality, so a reformatted but
    semantically equivalent signature still reads as stale, and a stale
    signature outside a fenced code block is invisible here.

    Args:
        root: Project root directory.
        symbols: Symbol names to check. If ``None``, check all symbols.

    Returns:
        List of dicts with ``symbol``, ``file``, ``doc_sig``,
        ``actual_sig``, and ``line`` keys.
    """
    ast_sigs = _extract_ast_signatures(root)
    doc_files = _collect_doc_files(root)
    if symbols is None:
        sym_set = {qk.rsplit(".", 1)[-1] for qk in ast_sigs}
    else:
        sym_set = set(symbols)
    # Build reverse index: bare name → list of (qualified_key, sig)
    bare_index: dict[str, list[str]] = {}
    for qkey in ast_sigs:
        bare = qkey.rsplit(".", 1)[-1]
        bare_index.setdefault(bare, []).append(qkey)
    stale: list[StaleSignature] = []
    for doc_file in doc_files:
        doc_sigs = _extract_doc_signatures(doc_file, sym_set, root)
        for entry in doc_sigs:
            sym_name = entry["symbol"]
            qkeys = bare_index.get(sym_name, [])
            if not qkeys:
                continue
            doc_sig = entry["doc_sig"].strip()
            # Conservative: report stale only if NO qualified match agrees
            if all(ast_sigs[qk].strip() != doc_sig for qk in qkeys):
                entry["actual_sig"] = ast_sigs[qkeys[0]]
                stale.append(entry)
    return stale


def analyze_doc_impact(
    root: Path,
    symbols: list[str],
) -> DocImpactResult:
    """Full doc impact analysis for a set of symbols.

    Combines doc refs, undocumented detection, and stale
    signature detection.

    Caveat (canonical) — all three signals rest on a **purely lexical**
    matching, never a semantic one. A symbol counts as mentioned when its
    bare name appears between backticks or in a Markdown heading, and a
    documented signature is only compared inside a fenced code block. No
    meaning is read: a purely semantic change leaves this output identical
    byte for byte, and a bare name-drop of the symbol anywhere in the prose
    is enough to remove it from ``undocumented``.

    Read the result as a list of pages to read, not a proof that the
    documentation is correct or up to date. Never use it as a non-regression
    oracle: an unchanged output proves nothing about the prose still telling
    the truth — a human review remains the only verdict on doc correctness.

    Limits — what this tool does not detect:

    1. A **semantic** change at unchanged name. Rewrite what a symbol means
       without touching its name and every signal stays identical, byte for
       byte: nothing here reports the prose that now lies.
    2. A bare **name-drop** counted as documentation. A single backticked
       mention, even in an unrelated sentence, is enough to drop the symbol
       from ``undocumented`` — presence is not coverage.
    3. ``undocumented`` is not a non-regression **oracle**. An empty or
       unchanged result proves nothing about documentation drift.

    When the semantics of a symbol change while its name does not, re-read by
    hand every page listed in ``doc_refs``: that manual pass is the one thing
    this tool cannot do for you. See ``docs/explanation/doc_impact_limits.md``.

    Args:
        root: Project root directory.
        symbols: Symbol names to analyze.

    Returns:
        Dict with ``doc_refs``, ``undocumented``, ``stale_signatures``.
    """
    refs = find_doc_refs(root, symbols)
    symbol_nodes = _index_symbol_nodes(root)
    return {
        "doc_refs": refs,
        "undocumented": find_undocumented(refs, symbol_nodes),
        "stale_signatures": find_stale_signatures(root, symbols),
    }
