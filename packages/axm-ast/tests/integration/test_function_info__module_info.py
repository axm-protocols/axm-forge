"""Public-API drivers for module/function lookup behind cross-module resolution.

Previously imported ``axm_ast.core.flows._find_source_module`` and
``_try_resolve_callee`` directly. The same scenarios are now exercised
through ``find_module_for_symbol`` (public analyzer surface) and
``trace_flow(cross_module=True)`` on a real fixture package.
"""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package, find_module_for_symbol
from axm_ast.core.flows import trace_flow


def test_find_source_module_by_symbol(tmp_path: Path) -> None:
    """PackageInfo with known function → public lookup returns its ModuleInfo."""
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    handler_dir = pkg_dir / "core"
    handler_dir.mkdir()
    (handler_dir / "__init__.py").write_text("")
    handler_py = handler_dir / "handler.py"
    handler_py.write_text("def process(): pass\n")

    pkg = analyze_package(pkg_dir)
    result = find_module_for_symbol(pkg, "process")
    assert result is not None
    assert result.path == handler_py.resolve()


class TestTryResolveCallee:
    """Public-API tests for cross-module resolution skipping local symbols."""

    def test_local_callee_not_cross_resolved(self, tmp_path: Path) -> None:
        """A function calling another LOCAL function → trace step has no
        ``resolved_module`` (cross-module resolution skips local symbols)."""
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "utils.py").write_text(
            "def local_fn():\n    pass\n\ndef caller():\n    local_fn()\n"
        )

        pkg = analyze_package(pkg_dir)
        steps, _ = trace_flow(pkg, "caller", cross_module=True, max_depth=3)
        names = {s.name for s in steps}
        assert {"caller", "local_fn"} <= names

        local_step = next(s for s in steps if s.name == "local_fn")
        # Local lookups never go through cross-module resolution → no
        # resolved_module is attached (that field is only set by the
        # cross-module path).
        assert local_step.resolved_module is None
