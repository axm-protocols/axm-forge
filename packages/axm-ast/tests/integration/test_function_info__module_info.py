"""Split from ``test_flows_cross_module.py``."""

from pathlib import Path

from axm_ast.models.calls import CallSite
from axm_ast.models.nodes import PackageInfo


def test_find_source_module_by_symbol(tmp_path: Path) -> None:
    """PackageInfo with known function → returns correct ModuleInfo."""
    from axm_ast.core.flows import _find_source_module
    from axm_ast.models.nodes import FunctionInfo, ModuleInfo

    root = tmp_path / "src"
    mod_path = root / "core" / "handler.py"
    mod_path.parent.mkdir(parents=True)
    mod_path.write_text("def process(): pass")

    func = FunctionInfo(name="process", line_start=1, line_end=1)
    mod = ModuleInfo(path=mod_path, functions=[func], classes=[], imports=[])
    pkg = PackageInfo(name="test", root=root, modules=[mod])

    result = _find_source_module(pkg, "process", "")
    assert result is not None
    assert result.path == mod_path


class TestTryResolveCallee:
    """Tests for the extracted _try_resolve_callee helper."""

    def test_try_resolve_callee_local(self, tmp_path: Path) -> None:
        """CallSite with locally-defined symbol → returns None (skip local)."""
        from axm_ast.core.flows import _try_resolve_callee
        from axm_ast.models.nodes import FunctionInfo, ModuleInfo, PackageInfo

        root = tmp_path / "src"
        mod_path = root / "utils.py"
        mod_path.parent.mkdir(parents=True)
        mod_path.write_text("def local_fn(): pass")

        func = FunctionInfo(name="local_fn", line_start=1, line_end=1)
        mod = ModuleInfo(path=mod_path, functions=[func], classes=[], imports=[])
        pkg = PackageInfo(name="test", root=root, modules=[mod])

        callee = CallSite(
            symbol="local_fn",
            module="utils",
            line=5,
            column=0,
            context="",
            call_expression="local_fn()",
        )
        result = _try_resolve_callee(callee, pkg)
        assert result is None
