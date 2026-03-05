"""Documentation tree dump for AI agents.

Discovers README, mkdocs config, and all docs/ markdown files,
then formats them as a single concatenated output.

Supports progressive disclosure via ``detail`` levels:

- ``toc``: heading tree + line count per page (~500 tokens)
- ``summary``: headings + first sentence per section
- ``full``: complete content (default, backward-compatible)

Example::

    >>> result = discover_docs(Path("."))
    >>> print(format_docs(result))
    📖 README.md
    ─────────────
    # My Project
    ...

    >>> result = discover_docs(Path("."), detail="toc")
    >>> result["pages"][0].keys()
    dict_keys(['path', 'headings', 'line_count'])
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

__all__ = [
    "build_docs_tree",
    "discover_docs",
    "extract_headings",
    "format_docs",
    "format_docs_json",
]

# ─── README variants (priority order) ───────────────────────────────────────

_README_NAMES = [
    "README.md",
    "readme.md",
    "README.rst",
    "readme.rst",
    "README.txt",
    "readme.txt",
    "README",
]


# ─── Heading extraction ──────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def extract_headings(content: str) -> list[dict[str, int | str]]:
    """Extract H1/H2/H3 headings from markdown content.

    Args:
        content: Raw markdown text.

    Returns:
        List of dicts with ``level`` (1-3) and ``text`` keys.
    """
    return [
        {"level": len(m.group(1)), "text": m.group(2).strip()}
        for m in _HEADING_RE.finditer(content)
    ]


def _extract_first_sentences(content: str) -> dict[str, str]:
    """Extract the first sentence after each heading.

    Args:
        content: Raw markdown text.

    Returns:
        Dict mapping heading text to its first sentence.
    """
    result: dict[str, str] = {}
    headings = list(_HEADING_RE.finditer(content))
    for i, match in enumerate(headings):
        heading_text = match.group(2).strip()
        # Section body = text between this heading and the next (or EOF)
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
        body = content[start:end].strip()
        sentence = _first_sentence(body)
        if sentence:
            result[heading_text] = sentence
    return result


def _first_sentence(text: str) -> str:
    """Extract the first non-empty meaningful sentence from text."""
    for line in text.splitlines():
        line = line.strip()
        # Skip empty lines, code fences, admonitions, list markers
        if not line or line.startswith("```") or line.startswith(">"):
            continue
        # Skip heading lines (shouldn't happen, but guard)
        if line.startswith("#"):
            continue
        return line
    return ""


# ─── Discovery ──────────────────────────────────────────────────────────────

_VALID_DETAIL_LEVELS = frozenset({"toc", "summary", "full"})


def discover_docs(
    root: Path,
    *,
    detail: str = "full",
    pages: list[str] | None = None,
) -> dict[str, Any]:
    """Walk project root, find README, mkdocs.yml, and docs/**/*.md.

    Args:
        root: Project root directory.
        detail: Detail level — ``toc``, ``summary``, or ``full``.
        pages: Optional list of page name substrings to filter.
            Case-insensitive. README and mkdocs are always included.

    Returns:
        Dict with readme, mkdocs, tree, and pages.

    Raises:
        ValueError: If *detail* is not a valid level.
    """
    if detail not in _VALID_DETAIL_LEVELS:
        msg = (
            f"Invalid detail level: {detail!r}"
            f" (choose from {sorted(_VALID_DETAIL_LEVELS)})"
        )
        raise ValueError(msg)

    return {
        "project": root.name,
        "readme": _find_readme(root),
        "mkdocs": _find_mkdocs(root),
        "tree": build_docs_tree(root / "docs"),
        "pages": _find_docs_pages(root, detail=detail, pages=pages),
    }


def _find_readme(root: Path) -> dict[str, str] | None:
    """Find README file by priority order."""
    for name in _README_NAMES:
        path = root / name
        if path.is_file():
            return {"path": name, "content": path.read_text(encoding="utf-8")}
    return None


def _find_mkdocs(root: Path) -> dict[str, str] | None:
    """Find mkdocs.yml or mkdocs.yaml."""
    for name in ("mkdocs.yml", "mkdocs.yaml"):
        path = root / name
        if path.is_file():
            return {"path": name, "content": path.read_text(encoding="utf-8")}
    return None


def _find_docs_pages(
    root: Path,
    *,
    detail: str = "full",
    pages: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Find markdown files in docs/ directory with progressive detail.

    Args:
        root: Project root.
        detail: One of ``toc``, ``summary``, ``full``.
        pages: Optional name substrings to filter (case-insensitive).
    """
    docs_dir = root / "docs"
    if not docs_dir.is_dir():
        return []

    result: list[dict[str, Any]] = []
    pages_lower = [p.lower() for p in pages] if pages else None

    for path in sorted(docs_dir.rglob("*.md")):
        rel = str(path.relative_to(root))

        # Apply pages filter
        if pages_lower and not any(sub in rel.lower() for sub in pages_lower):
            continue

        content = path.read_text(encoding="utf-8")

        if detail == "toc":
            result.append(
                {
                    "path": rel,
                    "headings": extract_headings(content),
                    "line_count": content.count("\n") + 1,
                }
            )
        elif detail == "summary":
            result.append(
                {
                    "path": rel,
                    "headings": extract_headings(content),
                    "summaries": _extract_first_sentences(content),
                    "line_count": content.count("\n") + 1,
                }
            )
        else:  # full
            result.append({"path": rel, "content": content})

    return result


# ─── Tree ────────────────────────────────────────────────────────────────────


def build_docs_tree(docs_path: Path) -> str | None:
    """Build an ASCII tree of the docs/ directory.

    Args:
        docs_path: Path to the docs/ directory.

    Returns:
        ASCII tree string, or None if docs/ doesn't exist.
    """
    if not docs_path.is_dir():
        return None

    lines: list[str] = ["docs/"]
    _walk_tree(docs_path, "", lines)
    return "\n".join(lines)


def _walk_tree(path: Path, prefix: str, lines: list[str]) -> None:
    """Recursively build tree lines."""
    children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
    for i, child in enumerate(children):
        is_last = i == len(children) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{child.name}")
        if child.is_dir():
            extension = "    " if is_last else "│   "
            _walk_tree(child, prefix + extension, lines)


# ─── Formatting ──────────────────────────────────────────────────────────────


def format_docs(result: dict[str, Any], *, tree_only: bool = False) -> str:
    """Format documentation dump as human-readable text.

    Args:
        result: Dict from discover_docs.
        tree_only: If True, show only the tree structure.

    Returns:
        Formatted text string.
    """
    parts: list[str] = []

    if tree_only:
        return _fmt_tree_only(result)

    _fmt_readme(result, parts)
    _fmt_mkdocs(result, parts)
    _fmt_tree_section(result, parts)
    _fmt_pages(result, parts)

    return "\n".join(parts)


def _fmt_tree_only(result: dict[str, Any]) -> str:
    """Format tree-only output."""
    parts: list[str] = []
    tree = result.get("tree")
    if tree:
        parts.append(f"📁 {result.get('project', 'project')}")
        parts.append(tree)
    readme = result.get("readme")
    if readme:
        parts.append(f"  📖 {readme['path']}")
    mkdocs = result.get("mkdocs")
    if mkdocs:
        parts.append(f"  ⚙️  {mkdocs['path']}")
    return "\n".join(parts)


def _fmt_readme(result: dict[str, Any], parts: list[str]) -> None:
    """Format README section."""
    readme = result.get("readme")
    if readme:
        parts.append(f"📖 {readme['path']}")
        parts.append("─" * 40)
        parts.append(readme["content"].rstrip())
        parts.append("")


def _fmt_mkdocs(result: dict[str, Any], parts: list[str]) -> None:
    """Format mkdocs section."""
    mkdocs = result.get("mkdocs")
    if mkdocs:
        parts.append(f"⚙️  {mkdocs['path']}")
        parts.append("─" * 40)
        parts.append(mkdocs["content"].rstrip())
        parts.append("")


def _fmt_tree_section(result: dict[str, Any], parts: list[str]) -> None:
    """Format tree section."""
    tree = result.get("tree")
    if tree:
        parts.append("📁 Documentation tree")
        parts.append("─" * 40)
        parts.append(tree)
        parts.append("")


def _fmt_pages(result: dict[str, Any], parts: list[str]) -> None:
    """Format documentation pages."""
    for page in result.get("pages", []):
        parts.append(f"📄 {page['path']}")
        parts.append("─" * 40)

        if "content" in page:
            # detail=full
            parts.append(page["content"].rstrip())
        else:
            # detail=toc or summary
            if page.get("line_count"):
                parts.append(f"({page['line_count']} lines)")
            for h in page.get("headings", []):
                indent = "  " * (h["level"] - 1)
                parts.append(f"{indent}{'#' * h['level']} {h['text']}")
            summaries = page.get("summaries", {})
            if summaries:
                parts.append("")
                for heading, sentence in summaries.items():
                    parts.append(f"  {heading}: {sentence}")
        parts.append("")


def format_docs_json(result: dict[str, Any]) -> dict[str, Any]:
    """Format documentation dump as JSON-serializable dict.

    Args:
        result: Dict from discover_docs.

    Returns:
        JSON-serializable dict.
    """
    return {
        "project": result.get("project"),
        "readme": result.get("readme"),
        "mkdocs": result.get("mkdocs"),
        "tree": result.get("tree"),
        "pages": result.get("pages", []),
    }
