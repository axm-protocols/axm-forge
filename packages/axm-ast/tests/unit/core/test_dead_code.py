"""Unit tests mirroring src/axm_ast/core/dead_code.py.

The scan-helper edge cases (_check_override, _scan_classes,
_scan_functions, _scan_methods, _ScanContext) are covered via the
public ``find_dead_code`` seam in
``tests/integration/test_analyze_package__find_dead_code.py``
(TestOverrides, TestExternalBaseOverrides, TestMixinBaseClass,
TestBasicDetection, TestExemptions, TestNamespaceModules,
TestIntraModuleClassRefs).

Only cases with no external boundary stay here: the in-memory
namespace probe and the pure formatter.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from axm_ast.core.dead_code import DeadSymbol, find_namespace_modules, format_dead_code


def _make_ns_pkg(modules: list[object]) -> MagicMock:
    """Create a minimal PackageInfo-like mock."""
    pkg = MagicMock()
    pkg.modules = modules
    return pkg


class TestLazyImportNamespaceDetectionUnit:
    """Pure unit cases (no filesystem I/O)."""

    def test_empty_package_returns_empty_set(self) -> None:
        pkg = _make_ns_pkg([])
        result = find_namespace_modules(pkg)

        assert result == set()


# ── format_dead_code ──


def test_format_empty() -> None:
    """Empty results → clean message."""
    assert format_dead_code([]) == "✅ No dead code detected."


# ── DeadSymbol model ──


def test_format_results() -> None:
    """Results → grouped output."""
    results = [
        DeadSymbol(name="foo", module_path="/a/b.py", line=10, kind="function"),
        DeadSymbol(name="bar", module_path="/a/b.py", line=20, kind="method"),
        DeadSymbol(name="baz", module_path="/a/c.py", line=5, kind="class"),
    ]
    output = format_dead_code(results)
    assert "3 dead symbol(s)" in output
    assert "foo" in output
    assert "bar" in output
    assert "baz" in output
    assert "/a/b.py" in output
    assert "/a/c.py" in output
