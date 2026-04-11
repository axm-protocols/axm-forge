from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from axm_ast.core.dead_code import _scan_classes, _ScanContext
from axm_ast.models.nodes import ModuleInfo

# ---------------------------------------------------------------------------
# Lightweight stubs
# ---------------------------------------------------------------------------


@dataclass
class _StubMethod:
    name: str
    line_start: int = 1
    decorators: list[str] = field(default_factory=list)


@dataclass
class _StubClass:
    name: str
    line_start: int = 1
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    methods: list[_StubMethod] = field(default_factory=list)


@dataclass
class _StubModule:
    path: Path = field(default_factory=lambda: Path("/fake/module.py"))
    classes: list[_StubClass] = field(default_factory=list)
    all_exports: list[str] | None = None


@dataclass
class _StubContext:
    entry_points: set[str] = field(default_factory=set)
    all_refs: set[str] = field(default_factory=set)
    extra_pkg: object | None = None
    namespace_modules: set[Path] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _patch_helpers(monkeypatch):
    """Patch all helpers called by _scan_classes so we test its logic only."""
    monkeypatch.setattr(
        "axm_ast.core.dead_code._collect_base_class_names", lambda _pkg: set()
    )
    monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])
    monkeypatch.setattr(
        "axm_ast.core.dead_code._is_exempt_class", lambda _cls, _mod: False
    )
    monkeypatch.setattr(
        "axm_ast.core.dead_code._has_intra_module_refs",
        lambda _name, _line, _mod: False,
    )
    monkeypatch.setattr(
        "axm_ast.core.dead_code._scan_methods",
        lambda _cls, _mod, _pkg, _ctx: [],
    )


# ---------------------------------------------------------------------------
# Unit tests — detection unchanged for mixed live/dead classes
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_patch_helpers")
class TestScanClassesDetection:
    """Modules with mixed live/dead classes — detection unchanged."""

    def test_class_in_entry_points_not_flagged(self, monkeypatch):
        """A class listed in entry_points is skipped entirely."""
        cls = _StubClass(name="Router")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext(entry_points={"Router"})

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Router" for s in result)

    def test_class_in_all_refs_not_flagged(self, monkeypatch):
        """A class present in all_refs is considered alive."""
        cls = _StubClass(name="Config")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext(all_refs={"Config"})

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Config" for s in result)

    def test_class_with_callers_not_flagged(self, monkeypatch):
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

    def test_class_with_callers_in_extra_pkg_not_flagged(self, monkeypatch):
        """A class found only via extra_pkg callers is alive."""
        cls = _StubClass(name="Helper")
        mod = _StubModule(classes=[cls])
        extra = MagicMock()
        ctx = _StubContext(extra_pkg=extra)

        call_count = 0

        def _find_callers(_pkg, name):
            nonlocal call_count
            call_count += 1
            # First call (primary pkg) returns empty, second (extra) returns hit
            if call_count == 1:
                return []
            return ["ext_caller"] if name == "Helper" else []

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _find_callers)

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "Helper" for s in result)

    def test_exempt_class_not_flagged(self, monkeypatch):
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

    def test_truly_dead_class_flagged(self, monkeypatch):
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

    def test_mixed_live_and_dead_classes(self, monkeypatch):
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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_patch_helpers")
class TestScanClassesEdgeCases:
    def test_class_used_as_base_not_flagged(self, monkeypatch):
        """A class that appears in the all_bases set is not flagged."""
        parent = _StubClass(name="BaseModel")
        child = _StubClass(name="Child", bases=["BaseModel"])
        mod = _StubModule(classes=[parent, child])
        ctx = _StubContext()

        # _collect_base_class_names returns bases gathered across the package
        monkeypatch.setattr(
            "axm_ast.core.dead_code._collect_base_class_names",
            lambda _pkg: {"BaseModel"},
        )

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        dead_names = [s.name for s in result]
        assert "BaseModel" not in dead_names

    def test_class_with_intra_module_refs_not_flagged(self, monkeypatch):
        """A class referenced only within same module is not dead."""
        cls = _StubClass(name="InternalHelper", line_start=5)
        mod = _StubModule(classes=[cls])
        ctx = _StubContext()

        monkeypatch.setattr(
            "axm_ast.core.dead_code._has_intra_module_refs",
            lambda name, _line, _mod: name == "InternalHelper",
        )

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        assert all(s.name != "InternalHelper" for s in result)

    def test_live_class_with_dead_methods(self, monkeypatch):
        """A live class (via callers) still reports dead methods from _scan_methods."""
        from axm_ast.core.dead_code import DeadSymbol

        cls = _StubClass(name="LiveClass")
        mod = _StubModule(classes=[cls])
        ctx = _StubContext()

        # Class is alive because it has callers (not via continue branch)
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

        result = _scan_classes(
            cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx)
        )

        # Class itself is NOT flagged
        assert all(s.kind != "class" for s in result)
        # But its dead method IS reported
        assert len(result) == 1
        assert result[0].name == "LiveClass.unused_method"
        assert result[0].kind == "method"

    def test_scan_methods_called_for_non_skipped_classes(self, monkeypatch):
        """_scan_methods is invoked for classes not short-circuited by continue."""
        cls_skipped = _StubClass(name="Skipped")
        cls_checked = _StubClass(name="Checked")
        mod = _StubModule(classes=[cls_skipped, cls_checked])
        # "Skipped" hits the continue branch; "Checked" does not
        ctx = _StubContext(entry_points={"Skipped"})

        calls: list[str] = []

        def _track_scan_methods(c, _mod, _pkg, _ctx):
            calls.append(c.name)
            return []

        monkeypatch.setattr("axm_ast.core.dead_code._scan_methods", _track_scan_methods)

        _scan_classes(cast(ModuleInfo, mod), MagicMock(), cast(_ScanContext, ctx))

        assert "Skipped" not in calls
        assert "Checked" in calls
