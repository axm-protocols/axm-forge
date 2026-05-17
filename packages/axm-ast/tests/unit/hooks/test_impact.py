from __future__ import annotations

import pytest

from axm_ast.hooks.impact import ImpactHook


def test_impact_module_all_exports():
    """DocImpactHook must be listed in __all__."""
    from axm_ast.hooks.impact import __all__

    assert "DocImpactHook" in __all__


def test_import_star_exposes_doc_impact_hook():
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
        from axm_ast.hooks.impact import ImpactHook

        hook = ImpactHook()
        result = hook.execute({})
        assert not result.success
        assert "symbol" in (result.error or "").lower()
