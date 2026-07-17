"""Unit tests for axm_anvil.core.callers.rewrite_caller_text."""

from __future__ import annotations

from axm_anvil.core.callers import (
    _find_import_line,
    _rewrite_module_import_caller,
    rewrite_caller_text,
)


def test_rewrite_caller_text_simple_from_import() -> None:
    """AC2: a plain single-line `from pkg.old import Foo` is rewritten to
    `pkg.new` (regression guard for the CST discovery change)."""
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


def test_rewrite_caller_text_multiline_import() -> None:
    """AC1: a multi-line ``from mod import (\\n foo,\\n bar,\\n)`` caller has its
    moved symbol redirected to ``new_module`` and emits one CallerRewrite."""
    text = "from pkg.old import (\n    Foo,\n    Bar,\n)\n\nFoo()\nBar()\n"

    new_text, rewrites = rewrite_caller_text(text, "pkg.old", "pkg.new", ["Foo"])

    assert "from pkg.new import Foo" in new_text
    # The unmoved name stays bound to the old module.
    assert "Bar" in new_text
    assert len(rewrites) == 1
    # The single rewrite records the multi-line span as the old import surface.
    entry = rewrites[0]
    assert "from pkg.old import" in entry.old
    assert entry.new == "from pkg.new import Foo"


def test_find_import_line_matches_bound_name() -> None:
    """AC1: with two `from old import` lines, `_find_import_line` returns the one
    that actually binds the requested name, not merely the first from-import."""
    text = "from pkg.old import Foo\nfrom pkg.old import Bar\n"

    located = _find_import_line(text, "pkg.old", ["Bar"])

    assert located is not None
    assert located[0] == 2
    assert located[1] == "from pkg.old import Bar"


def test_rewrite_module_import_caller_reports_alias_line() -> None:
    """AC2: an aliased `import old as om` caller reports the real source line and
    the literal alias-import text instead of hard-coded line=1 / `import old`."""
    text = "import os\nimport pkg.old as om\n\nx = om.Foo()\n"

    _new_text, rewrites = _rewrite_module_import_caller(
        text, "pkg.old", "pkg.new", ["Foo"]
    )

    assert len(rewrites) == 1
    entry = rewrites[0]
    assert entry.line == 2
    assert entry.old == "import pkg.old as om"
    assert entry.new == "import pkg.new"


def test_rewrite_caller_text_multiple_import_lines() -> None:
    """AC3: two distinct matching `from old import` statements yield one record
    each rather than a single collapsed record."""
    text = "from pkg.old import Foo\nfrom pkg.old import Bar\n\nFoo()\nBar()\n"

    _new_text, rewrites = rewrite_caller_text(
        text, "pkg.old", "pkg.new", ["Foo", "Bar"]
    )

    assert len(rewrites) == 2
    assert sorted(r.line for r in rewrites) == [1, 2]
    assert {r.old for r in rewrites} == {
        "from pkg.old import Foo",
        "from pkg.old import Bar",
    }
