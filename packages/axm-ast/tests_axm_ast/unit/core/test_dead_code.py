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

from axm_ast.core.dead_code import (
    DeadSymbol,
    find_dead_code,
    find_namespace_modules,
    format_dead_code,
)


def test_find_dead_code_docstring_documents_homonym_fn() -> None:
    """AC1: docstring warns about the name-only homonym false negative.

    A dead symbol sharing a name with a live one may be reported as live
    because references are matched by name only. The docstring must carry
    a ``.. warning::`` block documenting this limitation, mirroring the
    ``find_callers`` style.
    """
    doc = find_dead_code.__doc__
    assert doc is not None
    assert ".. warning::" in doc
    assert "name" in doc.lower()
    assert (
        "homonym" in doc.lower()
        or "like-named" in doc.lower()
        or "shares a name" in doc.lower()
        or "sharing a name" in doc.lower()
    )


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


def test_documented_dead_symbol_renders_coordination_notice() -> None:
    """AC3, AC6: documented dead code requires a coordinated docs update."""
    symbol = DeadSymbol(
        name="retired_api",
        module_path="src/sample/core.py",
        line=12,
        kind="function",
        documentation_references=["README.md", "docs/api/retired.md"],
    )

    output = format_dead_code([symbol])

    assert symbol.requires_documentation_update is True
    assert "README.md" in output
    assert "docs/api/retired.md" in output
    assert "update or remove" in output.lower()


def test_unreferenced_dead_symbol_preserves_legacy_rendering() -> None:
    """AC4: undocumented dead code keeps empty metadata and legacy output."""
    symbol = DeadSymbol(
        name="foo",
        module_path="/a/b.py",
        line=10,
        kind="function",
    )

    output = format_dead_code([symbol])

    assert symbol.documentation_references == []
    assert symbol.requires_documentation_update is False
    assert output == (
        "💀 1 dead symbol(s) found:\n\n  📄 /a/b.py\n    L  10  function    foo\n"
    )
