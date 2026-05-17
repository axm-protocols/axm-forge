"""Split from ``test_git_coupling.py``."""

import subprocess
from pathlib import Path

import pytest

from axm_ast.core.impact import analyze_impact
from tests.integration._helpers import (
    _make_import_heuristic_project,
    _make_project_with_test_callers,
    _make_project_with_test_callers__from_impact_test_filter,
)


def _find_git_root(start: Path) -> Path | None:
    """Walk up from *start* looking for a `.git` directory."""
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with a default branch and user config."""
    subprocess.run(
        ["git", "init"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        capture_output=True,
        check=True,
    )


def _commit(path: Path, files: list[str], message: str) -> None:
    """Stage files and commit."""
    for f in files:
        subprocess.run(
            ["git", "add", f],
            cwd=path,
            capture_output=True,
            check=True,
        )
    subprocess.run(
        ["git", "commit", "-m", message, "--allow-empty"],
        cwd=path,
        capture_output=True,
        check=True,
    )


def test_impact_has_git_coupled_field(tmp_path: Path) -> None:
    """analyze_impact result includes git_coupled field."""
    from axm_ast.core.impact import analyze_impact

    root = tmp_path / "project"
    root.mkdir()
    _init_git_repo(root)

    # Create a package
    pkg = root / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "core.py").write_text(
        '"""Core."""\ndef helper() -> None:\n    """Help."""\n    pass\n'
    )
    _commit(root, ["pkg/__init__.py", "pkg/core.py"], "init")

    result = analyze_impact(pkg, "helper", project_root=root)
    assert "git_coupled" in result
    assert isinstance(result["git_coupled"], list)


def test_impact_git_coupled_with_history(tmp_path: Path) -> None:
    """Symbol in file with coupling history → git_coupled is populated."""
    from axm_ast.core.impact import analyze_impact

    root = tmp_path / "project"
    root.mkdir()
    _init_git_repo(root)

    # Create a package
    pkg = root / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "core.py").write_text(
        '"""Core."""\ndef helper() -> None:\n    """Help."""\n    pass\n'
    )
    (pkg / "utils.py").write_text('"""Utils."""\n')
    _commit(root, ["pkg/__init__.py", "pkg/core.py", "pkg/utils.py"], "init")

    # Co-change core.py + utils.py 5 times
    for i in range(5):
        (pkg / "core.py").write_text(
            f'"""Core v{i + 2}."""\ndef helper() -> None:\n    """Help."""\n    pass\n'
        )
        (pkg / "utils.py").write_text(f'"""Utils v{i + 2}."""\n')
        _commit(root, ["pkg/core.py", "pkg/utils.py"], f"co-change {i}")

    result = analyze_impact(pkg, "helper", project_root=root)
    assert len(result["git_coupled"]) >= 1
    coupled_files = [c["file"] for c in result["git_coupled"]]
    assert any("utils" in f for f in coupled_files)


@pytest.mark.skipif(
    not _find_git_root(Path(__file__).resolve()),
    reason="Not in a git repo",
)
def test_impact_on_real_symbol_has_coupling() -> None:
    """Dogfood: analyze_impact on real symbol includes git_coupled."""
    from axm_ast.core.impact import analyze_impact

    root = Path(__file__).resolve().parents[2]
    ast_dir = root / "src" / "axm_ast"
    if ast_dir.exists():
        result = analyze_impact(ast_dir, "get_package", project_root=root)
        # Just verify the field exists, coupling may or may not have results
        assert "git_coupled" in result
        assert isinstance(result["git_coupled"], list)


def _make_project(tmp_path: Path) -> Path:
    """Create a typical project with init, module, and tests."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""Pkg."""\nfrom .core import helper\n\n__all__ = ["helper"]\n'
    )
    (pkg / "core.py").write_text(
        '"""Core module."""\n'
        "def helper(x: int) -> int:\n"
        '    """Help."""\n'
        "    return x + 1\n"
        "\n"
        "def _private() -> None:\n"
        '    """Private."""\n'
        "    pass\n"
    )
    (pkg / "cli.py").write_text(
        '"""CLI."""\n'
        "def main() -> None:\n"
        '    """Main."""\n'
        "    helper(42)\n"
        "\n"
        "def other() -> None:\n"
        '    """Other."""\n'
        "    helper(99)\n"
    )
    # Tests directory
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text(
        '"""Test core."""\ndef test_helper() -> None:\n    """Test."""\n    helper(1)\n'
    )
    (tests / "test_cli.py").write_text(
        '"""Test CLI."""\ndef test_main() -> None:\n    """Test."""\n    main()\n'
    )
    return pkg


def _make_dotted_project(tmp_path: Path) -> Path:
    """Create a project with classes, methods, properties, and nested classes."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "models.py").write_text(
        '"""Models."""\n'
        "class Foo:\n"
        '    """Foo class."""\n'
        "\n"
        "    def bar(self, x: int) -> int:\n"
        '        """Bar method."""\n'
        "        return x + 1\n"
        "\n"
        "    @property\n"
        "    def my_prop(self) -> str:\n"
        '        """A property."""\n'
        '        return "hello"\n'
    )
    (pkg / "nested.py").write_text(
        '"""Nested classes."""\n'
        "class Outer:\n"
        '    """Outer class."""\n'
        "\n"
        "    class Inner:\n"
        '        """Inner class."""\n'
        "\n"
        "        def method(self) -> None:\n"
        '            """Inner method."""\n'
        "            pass\n"
    )
    (pkg / "use.py").write_text(
        '"""Usage module."""\n'
        "def call_bar() -> None:\n"
        '    """Call bar."""\n'
        "    f = Foo()\n"
        "    f.bar(42)\n"
    )
    return pkg


def _make_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a workspace with two packages: pkg_a depends on pkg_b.

    Layout:
        workspace/
        ├── pkg_b/
        │   ├── __init__.py   (exports shared_model via __all__)
        │   └── models.py     (defines shared_model)
        └── pkg_a/
            ├── __init__.py
            └── consumer.py   (imports shared_model from pkg_b)

    Returns (workspace, pkg_a, pkg_b).
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # pkg_b — the provider
    pkg_b = workspace / "pkg_b"
    pkg_b.mkdir()
    (pkg_b / "__init__.py").write_text(
        '"""Package B."""\nfrom .models import shared_model\n\n'
        '__all__ = ["shared_model"]\n'
    )
    (pkg_b / "models.py").write_text(
        '"""Models."""\n'
        "def shared_model(x: int) -> int:\n"
        '    """Shared model used across packages."""\n'
        "    return x * 2\n"
        "\n"
        "def _private_helper() -> None:\n"
        '    """Private — not in __all__."""\n'
        "    pass\n"
    )

    # pkg_a — the consumer
    pkg_a = workspace / "pkg_a"
    pkg_a.mkdir()
    (pkg_a / "__init__.py").write_text('"""Package A."""\n')
    (pkg_a / "consumer.py").write_text(
        '"""Consumer."""\n'
        "from pkg_b import shared_model\n"
        "\n"
        "def process() -> int:\n"
        '    """Process using shared model."""\n'
        "    return shared_model(42)\n"
    )

    return workspace, pkg_a, pkg_b


class TestImpactEdgeCases:
    """Edge cases for impact analysis."""

    def test_symbol_no_callers(self, tmp_path: Path) -> None:
        """Defined but never called → LOW."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""Pkg."""\ndef lonely() -> None:\n    """Lonely."""\n    pass\n'
        )
        result = analyze_impact(pkg, "lonely", project_root=tmp_path)
        assert result["score"] == "LOW"
        assert result["callers"] == []

    def test_private_symbol(self, tmp_path: Path) -> None:
        """Private symbol impact analysis works."""
        pkg_dir = _make_project(tmp_path)
        result = analyze_impact(pkg_dir, "_private", project_root=tmp_path)
        assert result["score"] == "LOW"

    def test_method_impact(self, tmp_path: Path) -> None:
        """Method name impact detection."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""Pkg."""\n'
            "class Calc:\n"
            '    """Calc."""\n'
            "    def add(self, x: int) -> int:\n"
            '        """Add."""\n'
            "        return x\n"
        )
        (pkg / "use.py").write_text(
            '"""Use."""\n'
            "def go() -> None:\n"
            '    """Go."""\n'
            "    c = Calc()\n"
            "    c.add(1)\n"
        )
        result = analyze_impact(pkg, "add", project_root=tmp_path)
        assert len(result["callers"]) >= 1


def test_import_heuristic_skipped_in_analyze(tmp_path: Path) -> None:
    """When caller-based test_files is non-empty, heuristic does NOT run."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""Pkg."""\ndef helper() -> None:\n    """Help."""\n    pass\n'
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    # This test directly references "helper" → map_tests will find it
    (tests / "test_pkg.py").write_text(
        '"""Test."""\n'
        "from pkg import helper\n"
        "\n"
        "def test_helper() -> None:\n"
        '    """Test."""\n'
        "    helper()\n"
    )
    result = analyze_impact(pkg, "helper", project_root=tmp_path)
    assert "test_pkg.py" in result["test_files"]
    # Heuristic should not have run
    assert result.get("test_files_by_import") is None


def test_full_analyze_impact_with_heuristic(tmp_path: Path) -> None:
    """Integration: analyze_impact returns test_files_by_import."""
    pkg = _make_import_heuristic_project(tmp_path)
    result = analyze_impact(pkg, "InternalCfg", project_root=tmp_path)
    # InternalCfg has no callers in the package code
    assert result["callers"] == []
    # map_tests won't find it (name doesn't appear in test files)
    assert result["test_files"] == []
    # But the heuristic should find test_models.py via module import
    assert "test_files_by_import" in result
    assert "test_models.py" in result["test_files_by_import"]


class TestDottedSymbol:
    """Tests for dotted symbol resolution (Class.method)."""

    def test_impact_dotted_method(self, tmp_path: Path) -> None:
        """Dotted method returns non-null definition with kind=method."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo.bar", project_root=tmp_path)
        assert result["definition"] is not None
        assert result["definition"]["kind"] in ("method", "function")
        assert result["definition"]["line"] > 0

    def test_impact_dotted_callers(self, tmp_path: Path) -> None:
        """Dotted method finds callers that call instance.method()."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo.bar", project_root=tmp_path)
        assert len(result["callers"]) >= 1

    def test_impact_class_still_works(self, tmp_path: Path) -> None:
        """Bare class name still works after dotted support."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo", project_root=tmp_path)
        assert result["definition"] is not None
        assert result["definition"]["kind"] == "class"

    def test_impact_dotted_nonexistent(self, tmp_path: Path) -> None:
        """Non-existent method returns definition=None without crashing."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo.nonexistent", project_root=tmp_path)
        assert result["definition"] is None

    def test_impact_dotted_property(self, tmp_path: Path) -> None:
        """Property is resolved like a method."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo.my_prop", project_root=tmp_path)
        assert result["definition"] is not None
        assert result["definition"]["kind"] == "property"

    def test_impact_dotted_nested(self, tmp_path: Path) -> None:
        """Nested class method (Outer.Inner.method) — best-effort resolution."""
        pkg_dir = _make_dotted_project(tmp_path)
        # Should not crash; best-effort resolution
        result = analyze_impact(pkg_dir, "Outer.Inner.method", project_root=tmp_path)
        # We accept either a found definition or None — main thing is no crash
        assert isinstance(result, dict)
        assert "definition" in result

    def test_impact_on_real_symbol(self) -> None:
        """Dogfood on get_package (primary entry point after cache migration)."""
        root = Path(__file__).parent.parent
        ast_dir = root / "src" / "axm_ast"
        if ast_dir.exists():
            result = analyze_impact(ast_dir, "get_package", project_root=root)
            assert result["score"] in ("HIGH", "MEDIUM")
            assert len(result["callers"]) >= 1


def test_exclude_tests_preserves_score(tmp_path: Path) -> None:
    """Score is computed on the FULL caller set before filtering."""
    pkg_dir = _make_project_with_test_callers(tmp_path)
    result_full = analyze_impact(
        pkg_dir, "helper", project_root=tmp_path, exclude_tests=False
    )
    result_filtered = analyze_impact(
        pkg_dir, "helper", project_root=tmp_path, exclude_tests=True
    )
    assert result_filtered["score"] == result_full["score"]


def test_all_callers_are_tests(tmp_path: Path) -> None:
    """Symbol only used in tests → empty callers, score still computed."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "core.py").write_text(
        '"""Core."""\ndef internal() -> None:\n    """Internal."""\n    pass\n'
    )
    (pkg / "test_core.py").write_text(
        '"""Test."""\ndef test_it() -> None:\n    """Test."""\n    internal()\n'
    )
    result_full = analyze_impact(
        pkg, "internal", project_root=tmp_path, exclude_tests=False
    )
    result_filtered = analyze_impact(
        pkg, "internal", project_root=tmp_path, exclude_tests=True
    )
    assert result_filtered["callers"] == []
    assert result_filtered["score"] == result_full["score"]


def test_no_test_callers(tmp_path: Path) -> None:
    """No test callers → output identical with or without flag."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "core.py").write_text(
        '"""Core."""\ndef helper() -> None:\n    """Help."""\n    pass\n'
    )
    (pkg / "cli.py").write_text(
        '"""CLI."""\ndef main() -> None:\n    """Main."""\n    helper()\n'
    )
    result_with = analyze_impact(
        pkg, "helper", project_root=tmp_path, exclude_tests=True
    )
    result_without = analyze_impact(
        pkg, "helper", project_root=tmp_path, exclude_tests=False
    )
    assert result_with["callers"] == result_without["callers"]


class TestCrossPackageImpact:
    """Tests for cross-package blast radius detection (AXM-797)."""

    def test_cross_package_deps_detected(self, tmp_path: Path) -> None:
        """Symbol in __all__ imported by sibling → in cross_package_impact."""
        workspace, _pkg_a, pkg_b = _make_workspace(tmp_path)
        result = analyze_impact(pkg_b, "shared_model", project_root=workspace)
        cross = result.get("cross_package_impact", [])
        # pkg_a imports shared_model from pkg_b → must appear
        assert any("pkg_a" in entry for entry in cross), (
            f"Expected pkg_a in cross_package_impact, got {cross}"
        )

    def test_no_cross_package_when_symbol_private(self, tmp_path: Path) -> None:
        """Private symbol (not in __all__) → cross_package_impact empty."""
        workspace, _pkg_a, pkg_b = _make_workspace(tmp_path)
        result = analyze_impact(pkg_b, "_private_helper", project_root=workspace)
        cross = result.get("cross_package_impact", [])
        assert cross == [], (
            f"Private symbol should have no cross-package impact, got {cross}"
        )

    def test_circular_dependency_no_infinite_loop(self, tmp_path: Path) -> None:
        """Circular dep (pkg_a ↔ pkg_b) terminates without infinite loop."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # pkg_b imports from pkg_a
        pkg_b = workspace / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text(
            '"""Package B."""\nfrom .core import func_b\n\n__all__ = ["func_b"]\n'
        )
        (pkg_b / "core.py").write_text(
            '"""Core B."""\n'
            "from pkg_a import func_a\n"
            "\n"
            "def func_b() -> int:\n"
            '    """B calls A."""\n'
            "    return func_a() + 1\n"
        )

        # pkg_a imports from pkg_b
        pkg_a = workspace / "pkg_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text(
            '"""Package A."""\nfrom .core import func_a\n\n__all__ = ["func_a"]\n'
        )
        (pkg_a / "core.py").write_text(
            '"""Core A."""\n'
            "from pkg_b import func_b\n"
            "\n"
            "def func_a() -> int:\n"
            '    """A calls B."""\n'
            "    return func_b() + 1\n"
        )

        result = analyze_impact(pkg_b, "func_b", project_root=workspace)
        cross = result.get("cross_package_impact", [])
        # Both packages should appear (mutual dependency), no hang
        assert any("pkg_a" in entry for entry in cross), (
            f"Expected pkg_a in circular cross-package impact, got {cross}"
        )

    def test_symbol_not_imported_excluded(self, tmp_path: Path) -> None:
        """pkg_a depends on pkg_b but doesn't import the changed symbol → not listed."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        pkg_b = workspace / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "__init__.py").write_text(
            '"""Package B."""\n'
            "from .models import used_func, unused_func\n\n"
            '__all__ = ["used_func", "unused_func"]\n'
        )
        (pkg_b / "models.py").write_text(
            '"""Models."""\n'
            "def used_func() -> int:\n"
            '    """Used by pkg_a."""\n'
            "    return 1\n"
            "\n"
            "def unused_func() -> int:\n"
            '    """Not imported by pkg_a."""\n'
            "    return 2\n"
        )

        pkg_a = workspace / "pkg_a"
        pkg_a.mkdir()
        (pkg_a / "__init__.py").write_text('"""Package A."""\n')
        (pkg_a / "consumer.py").write_text(
            '"""Consumer."""\n'
            "from pkg_b import used_func\n"
            "\n"
            "def run() -> int:\n"
            '    """Only uses used_func."""\n'
            "    return used_func()\n"
        )

        result = analyze_impact(pkg_b, "unused_func", project_root=workspace)
        cross = result.get("cross_package_impact", [])
        assert not any("pkg_a" in entry for entry in cross), (
            f"pkg_a should NOT appear for unused_func, got {cross}"
        )


def test_impact_exclude_tests_backward_compat(tmp_path: Path) -> None:
    """exclude_tests=True produces same result as test_filter='none'."""
    pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
    result_legacy = analyze_impact(
        pkg, "target_fn", project_root=tmp_path, exclude_tests=True
    )
    result_new = analyze_impact(
        pkg, "target_fn", project_root=tmp_path, test_filter="none"
    )
    assert result_legacy["callers"] == result_new["callers"]
    assert result_legacy.get("type_refs", []) == result_new.get("type_refs", [])


def _make_pkg(tmp_path: Path, *, with_override: bool, n_callers: int) -> Path:
    pkg_root = tmp_path / "fakepkg"
    src = pkg_root / "src" / "fakepkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "core.py").write_text("def target() -> int:\n    return 1\n")

    body = "from fakepkg.core import target\n\n"
    for i in range(n_callers):
        body += f"def caller_{i}() -> int:\n    return target()\n\n"
    (src / "callers.py").write_text(body)

    pyproject = '[project]\nname = "fakepkg"\nversion = "0.1.0"\n'
    if with_override:
        pyproject += "\n[tool.axm-ast.impact]\nhigh_threshold = 2\n"
    (pkg_root / "pyproject.toml").write_text(pyproject)
    return pkg_root / "src" / "fakepkg"


def test_pyproject_override_lowers_high_threshold(tmp_path: Path) -> None:
    pkg_path = _make_pkg(tmp_path, with_override=True, n_callers=2)
    result = analyze_impact(pkg_path, "target")
    assert result["score"] == "HIGH"


def test_no_pyproject_section_uses_defaults(tmp_path: Path) -> None:
    pkg_path = _make_pkg(tmp_path, with_override=False, n_callers=2)
    result = analyze_impact(pkg_path, "target")
    assert result["score"] == "MEDIUM"
