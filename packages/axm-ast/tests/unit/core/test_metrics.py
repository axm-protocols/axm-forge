"""Unit tests for the language-agnostic structural metrics."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.metrics import compute_coupling, find_god_classes
from axm_ast.models.nodes import ClassInfo, FunctionInfo, ModuleInfo, PackageInfo


def _cls(name: str, *, lines: int, methods: int) -> ClassInfo:
    """Build a ClassInfo spanning *lines* with *methods* methods."""
    return ClassInfo(
        name=name,
        line_start=1,
        line_end=lines,
        methods=[
            FunctionInfo(name=f"m{i}", line_start=1, line_end=1) for i in range(methods)
        ],
    )


def _pkg(tmp_path: Path, *classes: ClassInfo) -> PackageInfo:
    """Build a single-module package containing *classes*."""
    mod = ModuleInfo(path=tmp_path / "m.ts", classes=list(classes))
    return PackageInfo(name="p", root=tmp_path, modules=[mod], dependency_edges=[])


class TestFindGodClasses:
    """``find_god_classes`` flags classes over the line/method thresholds."""

    def test_small_class_not_flagged(self, tmp_path: Path) -> None:
        """A class within both thresholds is not a god class."""
        pkg = _pkg(tmp_path, _cls("Small", lines=50, methods=5))
        assert find_god_classes(pkg) == []

    def test_too_many_methods_flagged(self, tmp_path: Path) -> None:
        """A class with more than max_methods is flagged."""
        pkg = _pkg(tmp_path, _cls("Big", lines=50, methods=16))
        god = find_god_classes(pkg)
        assert [g.name for g in god] == ["Big"]
        assert god[0].methods == 16

    def test_too_many_lines_flagged(self, tmp_path: Path) -> None:
        """A class longer than max_lines is flagged."""
        pkg = _pkg(tmp_path, _cls("Long", lines=600, methods=2))
        assert [g.name for g in find_god_classes(pkg)] == ["Long"]

    def test_custom_thresholds(self, tmp_path: Path) -> None:
        """Thresholds are configurable."""
        pkg = _pkg(tmp_path, _cls("X", lines=50, methods=6))
        assert find_god_classes(pkg, max_methods=5)


class TestComputeCoupling:
    """``compute_coupling`` derives fan-in/out from the dependency edges."""

    def test_fan_in_out_from_edges(self, tmp_path: Path) -> None:
        """Edges drive each module's fan-out (out-degree) and fan-in."""
        pkg = PackageInfo(
            name="p",
            root=tmp_path,
            modules=[],
            dependency_edges=[("a", "b"), ("a", "c"), ("d", "b")],
        )
        metrics = compute_coupling(pkg)
        by_mod = {m.module: m for m in metrics.per_module}
        assert by_mod["a"].fan_out == 2
        assert by_mod["b"].fan_in == 2
        assert metrics.max_fan_out == 2
        assert metrics.max_fan_in == 2

    def test_over_fan_out_threshold(self, tmp_path: Path) -> None:
        """``over_fan_out`` returns modules above the given threshold."""
        edges = [("hub", f"m{i}") for i in range(12)]
        pkg = PackageInfo(name="p", root=tmp_path, modules=[], dependency_edges=edges)
        over = compute_coupling(pkg).over_fan_out(10)
        assert [m.module for m in over] == ["hub"]

    def test_no_edges_is_zero(self, tmp_path: Path) -> None:
        """A package with no edges has zero maxima."""
        pkg = PackageInfo(name="p", root=tmp_path, modules=[], dependency_edges=[])
        metrics = compute_coupling(pkg)
        assert metrics.max_fan_out == 0
        assert metrics.max_fan_in == 0
