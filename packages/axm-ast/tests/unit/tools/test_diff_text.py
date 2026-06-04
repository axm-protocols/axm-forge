from __future__ import annotations

from axm_ast.tools.diff_text import render_diff_text

_DATA: dict[str, object] = {
    "added": [
        {
            "name": "new_fn",
            "kind": "function",
            "file": "core.py",
            "signature": "def new_fn(x: int) -> int",
        },
        {"name": "bare", "kind": "function", "file": "core.py", "signature": None},
    ],
    "removed": [
        {
            "name": "old_fn",
            "kind": "function",
            "file": "util.py",
            "signature": "def old_fn() -> None",
        },
    ],
    "modified": [
        {
            "name": "changed",
            "kind": "function",
            "file": "core.py",
            "old_signature": "def changed(a: int) -> int",
            "new_signature": "def changed(a: str) -> int",
        },
    ],
    "summary": {"added": 2, "removed": 1, "modified": 1},
}


def test_header_carries_counts() -> None:
    """Header is the ast_diff prefix with +added -removed ~modified counts."""
    text = render_diff_text(_DATA)
    assert text.startswith("ast_diff | +2 -1 ~1")


def test_added_signatures_present() -> None:
    """Added symbols are emitted with their full signature under a file header."""
    text = render_diff_text(_DATA)
    assert "## core.py" in text
    assert "+ def new_fn(x: int) -> int" in text


def test_added_without_signature_falls_back_to_name() -> None:
    """A signatureless symbol falls back to ``kind name``."""
    text = render_diff_text(_DATA)
    assert "+ function bare" in text


def test_removed_uses_minus_glyph() -> None:
    """Removed symbols are emitted with a ``-`` prefix under their file."""
    text = render_diff_text(_DATA)
    assert "## util.py" in text
    assert "- def old_fn() -> None" in text


def test_modified_shows_before_and_after() -> None:
    """Modified symbols carry both before and after signatures."""
    text = render_diff_text(_DATA)
    assert "~ changed: def changed(a: int) -> int → def changed(a: str) -> int" in text


def test_empty_diff_is_header_only() -> None:
    """An empty diff renders just the zero-count header."""
    text = render_diff_text({"added": [], "removed": [], "modified": [], "summary": {}})
    assert text == "ast_diff | +0 -0 ~0"
