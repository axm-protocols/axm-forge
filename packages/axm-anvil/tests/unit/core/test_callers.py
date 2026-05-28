"""Unit tests for axm_anvil.core.callers.rewrite_caller_text."""

from __future__ import annotations

from axm_anvil.core.callers import rewrite_caller_text


def test_rewrite_caller_text_simple_from_import() -> None:
    """AC2: a plain `from pkg.old import Foo` is rewritten to `pkg.new`."""
    text = "from pkg.old import Foo\n\nFoo()\n"

    new_text, rewrites = rewrite_caller_text(text, "pkg.old", "pkg.new", ["Foo"])

    assert "from pkg.new import Foo" in new_text
    assert "pkg.old" not in new_text
    assert len(rewrites) >= 1


def test_rewrite_caller_text_preserves_alias() -> None:
    """AC3: `from pkg.old import Foo as Bar` preserves `as Bar` after rewrite."""
    text = "from pkg.old import Foo as Bar\n\nBar()\n"

    new_text, _rewrites = rewrite_caller_text(text, "pkg.old", "pkg.new", ["Foo"])

    assert "from pkg.new import Foo as Bar" in new_text
    assert "pkg.old" not in new_text


def test_rewrite_caller_text_partial_import() -> None:
    """AC4: moving one symbol out of a multi-name import keeps the others."""
    text = "from pkg.old import A, Foo, B\n"

    new_text, _rewrites = rewrite_caller_text(text, "pkg.old", "pkg.new", ["Foo"])

    assert "from pkg.new import Foo" in new_text
    # The remaining names must stay on an old-module import line.
    assert (
        "from pkg.old import A, B" in new_text or "from pkg.old import B, A" in new_text
    )
    # Moved name no longer on the old-module line.
    assert "from pkg.old import A, Foo, B" not in new_text


def test_rewrite_caller_text_reports_old_new_line() -> None:
    """AC7: a rewrite records `line`, literal `old`, and literal `new`."""
    text = "from pkg.old import Foo\n"

    _new_text, rewrites = rewrite_caller_text(text, "pkg.old", "pkg.new", ["Foo"])

    assert len(rewrites) == 1
    entry = rewrites[0]
    assert entry.line == 1
    assert entry.old == "from pkg.old import Foo"
    assert entry.new == "from pkg.new import Foo"


def test_rewrite_caller_text_no_match_returns_unchanged() -> None:
    """AC8: a caller importing `Foo` from another module is untouched."""
    text = "from pkg.other import Foo\n\nFoo()\n"

    new_text, rewrites = rewrite_caller_text(text, "pkg.old", "pkg.new", ["Foo"])

    assert new_text == text
    assert rewrites == []


def test_rewrite_caller_text_multi_symbol_same_line() -> None:
    """AC4: two moved symbols on the same import line are rewritten together."""
    text = "from pkg.old import Foo, Bar\n"

    new_text, rewrites = rewrite_caller_text(text, "pkg.old", "pkg.new", ["Foo", "Bar"])

    assert "from pkg.new import" in new_text
    assert "Foo" in new_text
    assert "Bar" in new_text
    # Original old-module line fully removed.
    assert "from pkg.old import" not in new_text
    assert len(rewrites) >= 1
