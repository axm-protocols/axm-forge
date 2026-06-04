"""Text renderer for ``ast_docs`` output.

Renders the :func:`format_docs_json` payload as compact human-readable
text for the LLM, mirroring the glyph/header conventions of the sibling
``*_text`` renderers. Full-detail content (README, mkdocs, page bodies)
is reproduced verbatim — no truncation; the compaction is purely the
removal of JSON key/quote/escape overhead.
"""

from __future__ import annotations

from typing import TypedDict, cast

__all__ = ["render_docs_text"]


class _FileEntry(TypedDict, total=False):
    path: str
    content: str


class _Heading(TypedDict, total=False):
    level: int
    text: str


class _PageEntry(TypedDict, total=False):
    path: str
    content: str
    headings: list[_Heading]
    summaries: dict[str, str]
    line_count: int


class _DocsData(TypedDict, total=False):
    project: str
    readme: _FileEntry | None
    mkdocs: _FileEntry | None
    tree: str | None
    pages: list[_PageEntry]


def render_docs_text(data: dict[str, object], detail: str) -> str:
    """Render docs data as compact text for a given detail level.

    Args:
        data: Payload from :func:`format_docs_json`.
        detail: Detail level — ``toc``, ``summary``, or ``full``.

    Returns:
        Compact text rendering. Full bodies are reproduced verbatim.
    """
    typed = cast("_DocsData", data)
    pages = typed.get("pages") or []
    project = typed.get("project", "project")
    readme = typed.get("readme")
    mkdocs = typed.get("mkdocs")
    extras = (1 if readme else 0) + (1 if mkdocs else 0)
    header = f"ast_docs | {detail} | {project} | {len(pages)} pages +{extras}"

    lines: list[str] = [header]
    _append_file(lines, "\U0001f4d6", readme)
    _append_file(lines, "⚙", mkdocs)
    _append_tree(lines, typed.get("tree"))
    for page in pages:
        _append_page(lines, page, detail)
    return "\n".join(lines)


def _append_file(lines: list[str], glyph: str, entry: _FileEntry | None) -> None:
    """Append a verbatim README/mkdocs section if present."""
    if not entry:
        return
    content = entry.get("content", "").rstrip()
    lines.append(f"{glyph} {entry.get('path', '')}")
    if content:
        lines.append(content)


def _append_tree(lines: list[str], tree: object) -> None:
    """Append the docs/ ASCII tree if present."""
    if isinstance(tree, str) and tree:
        lines.append("\U0001f4c1 tree")
        lines.append(tree)


def _append_page(lines: list[str], page: _PageEntry, detail: str) -> None:
    """Append one page rendered per the requested detail level."""
    path = page.get("path", "")
    line_count = page.get("line_count")
    head = f"\U0001f4c4 {path}" + (f" ({line_count}L)" if line_count else "")
    lines.append(head)

    if detail == "full" or "content" in page:
        content = page.get("content", "").rstrip()
        if content:
            lines.append(content)
        return

    lines.extend(_render_headings(page.get("headings") or []))
    lines.extend(_render_summaries(page.get("summaries") or {}))


def _render_headings(headings: list[_Heading]) -> list[str]:
    """Render headings as an indented ``#``-prefixed tree."""
    out: list[str] = []
    for h in headings:
        level = h.get("level", 1)
        text = h.get("text", "")
        out.append(f"{'  ' * (level - 1)}{'#' * level} {text}")
    return out


def _render_summaries(summaries: dict[str, str]) -> list[str]:
    """Render per-heading first-sentence summaries."""
    return [f"  {heading}: {sentence}" for heading, sentence in summaries.items()]
