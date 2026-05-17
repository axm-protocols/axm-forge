"""Split from ``test_dead_code.py``."""

from typing import cast
from unittest.mock import MagicMock

import pytest

from axm_ast.core.dead_code import DeadSymbol, _scan_classes, _ScanContext
from axm_ast.models.nodes import ModuleInfo
from tests.unit._helpers import _StubClass, _StubContext, _StubModule


@pytest.mark.usefixtures("_patch_scan_classes_helpers")
def test_live_class_with_dead_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    """A live class (via callers) still reports dead methods from _scan_methods."""
    cls = _StubClass(name="LiveClass")
    mod = _StubModule(classes=[cls])
    ctx = _StubContext()

    monkeypatch.setattr(
        "axm_ast.core.callers.find_callers",
        lambda _pkg, name: ["a_caller"] if name == "LiveClass" else [],
    )

    dead_method = DeadSymbol(
        name="LiveClass.unused_method",
        module_path=str(mod.path),
        line=20,
        kind="method",
    )
    monkeypatch.setattr(
        "axm_ast.core.dead_code._scan_methods",
        lambda _cls, _mod, _pkg, _ctx: [dead_method],
    )

    result = _scan_classes(cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx))

    assert all(s.kind != "class" for s in result)
    assert len(result) == 1
    assert result[0].name == "LiveClass.unused_method"
    assert result[0].kind == "method"
