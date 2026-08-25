from __future__ import annotations

import pytest

from axm_ast.hooks.impact import DocImpactHook, ImpactHook


def test_impact_module_all_exports() -> None:
    """DocImpactHook must be listed in __all__."""
    from axm_ast.hooks.impact import __all__

    assert "DocImpactHook" in __all__


def test_import_star_exposes_doc_impact_hook() -> None:
    """'from axm_ast.hooks.impact import *' must make DocImpactHook available."""
    ns: dict[str, object] = {}
    exec("from axm_ast.hooks.impact import *", ns)  # noqa: S102
    assert "DocImpactHook" in ns


@pytest.fixture
def hook() -> ImpactHook:
    return ImpactHook()


class TestImpactHookUnit:
    """Pure unit cases (no filesystem I/O)."""

    def test_impact_hook_no_symbol(self) -> None:
        """Missing symbol param → HookResult.fail."""
        hook = ImpactHook()
        result = hook.execute({})
        assert not result.success
        assert "symbol" in (result.error or "").lower()


# ── ImpactHook execute tests (merged from test_hooks.py) ────────────────────


class TestImpactHookExecuteUnit:
    """Tests for ImpactHook — single and multi-symbol analysis."""

    def test_missing_symbol(self) -> None:
        """Fail when 'symbol' param is missing."""
        hook = ImpactHook()
        result = hook.execute({})
        assert not result.success
        assert result.error is not None
        assert "symbol" in result.error

    def test_invalid_path(self) -> None:
        """Fail when path doesn't exist."""
        hook = ImpactHook()
        result = hook.execute({}, symbol="Foo", path="/nonexistent/dir")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error


class TestDocImpactHookExecuteUnit:
    """Tests for DocImpactHook — single and multi-symbol doc impact analysis."""

    def test_missing_symbol(self) -> None:
        """Fail when 'symbol' param is missing."""
        hook = DocImpactHook()
        result = hook.execute({})
        assert not result.success
        assert result.error is not None
        assert "symbol" in result.error

    def test_invalid_path(self) -> None:
        """Fail when path doesn't exist."""
        hook = DocImpactHook()
        result = hook.execute({}, symbol="Foo", path="/nonexistent/dir")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error
