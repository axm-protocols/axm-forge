"""Tests for axm_ast.core.callers (find_callers)."""

from __future__ import annotations

from axm_ast.core.callers import find_callers


class TestFindCallersNameMatchLimitDoc:
    """AC1: name-only matching limitation is documented."""

    def test_find_callers_docstring_documents_namematch_limit(self) -> None:
        """AC1: docstring warns matching is by name only (receiver ignored).

        The docstring must surface that distinct receivers (``self.foo`` vs
        ``obj.foo`` vs bare ``foo``) collapse to the same name and may yield
        false-positive callers.
        """
        doc = find_callers.__doc__ or ""
        lowered = doc.lower()
        assert "name" in lowered
        assert "receiver" in lowered
        assert "false-positive" in lowered or "false positive" in lowered
