"""Unit tests for axm_ast.core.dead_code."""

from __future__ import annotations

from axm_ast.core.dead_code import find_dead_code


def test_find_dead_code_docstring_documents_homonym_fn() -> None:
    """AC1: docstring warns about the name-only homonym false negative.

    A dead symbol sharing a name with a live one may be reported as live
    because references are matched by name only. The docstring must carry
    a ``.. warning::`` block documenting this limitation, mirroring the
    ``find_callers`` style.
    """
    doc = find_dead_code.__doc__
    assert doc is not None
    assert ".. warning::" in doc
    assert "name" in doc.lower()
    assert (
        "homonym" in doc.lower()
        or "like-named" in doc.lower()
        or "shares a name" in doc.lower()
        or "sharing a name" in doc.lower()
    )
