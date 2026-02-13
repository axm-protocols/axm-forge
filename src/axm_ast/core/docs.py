"""Documentation tree dump for AI agents.

Discovers README, mkdocs config, and all docs/ markdown files,
then formats them as a single concatenated output.

Example::

    >>> result = discover_docs(Path("."))
    >>> print(format_docs(result))
    📖 README.md
    ─────────────
    # My Project
    ...

    📄 docs/index.md
    ─────────────
    # Home
    ...
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = [
    "build_docs_tree",
    "discover_docs",
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


# ─── Discovery ──────────────────────────────────────────────────────────────


def discover_docs(root: Path) -> dict[str, Any]:
    """Walk project root, find README, mkdocs.yml, and docs/**/*.md.

    Args:
        root: Project root directory.

    Returns:
        Dict with readme, mkdocs, tree, and pages.
    """
    return {
        "project": root.name,
        "readme": _find_readme(root),
        "mkdocs": _find_mkdocs(root),
        "tree": build_docs_tree(root / "docs"),
        "pages": _find_docs_pages(root),
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


def _find_docs_pages(root: Path) -> list[dict[str, str]]:
    """Find all markdown files in docs/ directory."""
    docs_dir = root / "docs"
    if not docs_dir.is_dir():
        return []

    pages: list[dict[str, str]] = []
    for path in sorted(docs_dir.rglob("*.md")):
        rel = path.relative_to(root)
        pages.append(
            {
                "path": str(rel),
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return pages


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
        parts.append(page["content"].rstrip())
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
