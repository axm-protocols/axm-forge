"""Unit tests for axm_ast.core.dead_code internals."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from axm_ast.core.dead_code import (
    _scan_classes,
    _ScanContext,
)
from axm_ast.models.nodes import (
    ModuleInfo,
)
from tests.unit._helpers import _StubClass, _StubContext, _StubModule


@pytest.mark.usefixtures("_patch_scan_classes_helpers")
class TestScanClassesDetection:
    """Modules with mixed live/dead classes — detection unchanged."""

    def test_class_in_entry_points_not_flagged(self) -> None:
        """A class listed in entry_points is skipped entirely."""
        cls = _StubClass(name="Router")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext(entry_points={"Router"})

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Router" for s in result)

    def test_class_in_all_refs_not_flagged(self) -> None:
        """A class present in all_refs is considered alive."""
        cls = _StubClass(name="Config")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext(all_refs={"Config"})

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Config" for s in result)

    def test_class_with_callers_not_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A class with callers in the primary package is alive."""
        cls = _StubClass(name="Service")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext()

        monkeypatch.setattr(
            "axm_ast.core.callers.find_callers",
            lambda _pkg, name: ["some_caller"] if name == "Service" else [],
        )

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Service" for s in result)

    def test_class_with_callers_in_extra_pkg_not_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A class found only via extra_pkg callers is alive."""
        cls = _StubClass(name="Helper")
        mod = _StubModule(classes=[cls])
        extra = MagicMock()
        ctx = _StubContext(extra_pkg=extra)

        def _find_callers(_pkg: object, name: str) -> list[str]:
            if _pkg is extra and name == "Helper":
                return ["ext_caller"]
            return []

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _find_callers)

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Helper" for s in result)

    def test_exempt_class_not_flagged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An exempt class (decorated, protocol, etc.) is not dead."""
        cls = _StubClass(name="Proto")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext()

        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_class", lambda c, m: True
        )

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Proto" for s in result)

    def test_truly_dead_class_flagged(self) -> None:
        """A class with no callers, not exempt, no intra-module refs is dead."""
        cls = _StubClass(name="Orphan", line_start=42)
        mod = _StubModule(classes=[cls])
        ctx = _StubContext()

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        dead_names = [s.name for s in result]
        assert "Orphan" in dead_names
        orphan = next(s for s in result if s.name == "Orphan")
        assert orphan.kind == "class"
        assert orphan.line == 42

    def test_mixed_live_and_dead_classes(self) -> None:
        """Only truly dead classes are flagged; alive ones are skipped."""
        alive_cls = _StubClass(name="Alive")
        dead_cls = _StubClass(name="Dead", line_start=10)
        mod = _StubModule(classes=[alive_cls, dead_cls])
        ctx = _StubContext(all_refs={"Alive"})

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        dead_names = [s.name for s in result]
        assert "Alive" not in dead_names
        assert "Dead" in dead_names


@pytest.mark.usefixtures("_patch_scan_classes_helpers")
def test_class_used_as_base_not_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    """A class that appears in the all_bases set is not flagged."""
    parent = _StubClass(name="BaseModel")
    child = _StubClass(name="Child", bases=["BaseModel"])
    mod = _StubModule(classes=[parent, child])
    ctx = _StubContext()

    monkeypatch.setattr(
        "axm_ast.core.dead_code._collect_base_class_names",
        lambda _pkg: {"BaseModel"},
    )

    result = _scan_classes(cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx))

    dead_names = [s.name for s in result]
    assert "BaseModel" not in dead_names


@pytest.mark.usefixtures("_patch_scan_classes_helpers")
def test_class_with_intra_module_refs_not_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A class referenced only within same module is not dead."""
    cls = _StubClass(name="InternalHelper", line_start=5)
    mod = _StubModule(classes=[cls])
    ctx = _StubContext()

    monkeypatch.setattr(
        "axm_ast.core.dead_code._has_intra_module_refs",
        lambda name, _line, _mod: name == "InternalHelper",
    )

    result = _scan_classes(cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx))

    assert all(s.name != "InternalHelper" for s in result)


@pytest.mark.usefixtures("_patch_scan_classes_helpers")
def test_scan_methods_called_for_non_skipped_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_scan_methods is invoked for classes not short-circuited by continue."""
    cls_skipped = _StubClass(name="Skipped")
    cls_checked = _StubClass(name="Checked")
    mod = _StubModule(classes=[cls_skipped, cls_checked])
    ctx = _StubContext(entry_points={"Skipped"})

    calls: list[str] = []

    def _track_scan_methods(c: Any, _mod: Any, _pkg: Any, _ctx: Any) -> list[Any]:
        calls.append(c.name)
        return []

    monkeypatch.setattr("axm_ast.core.dead_code._scan_methods", _track_scan_methods)

    _scan_classes(cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx))

    assert "Skipped" not in calls
    assert "Checked" in calls
