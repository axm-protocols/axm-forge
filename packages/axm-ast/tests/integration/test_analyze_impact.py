"""Split from ``test_git_coupling.py``."""

import subprocess
import warnings
from pathlib import Path

import pytest

from axm_ast.core.impact import ImpactResult, analyze_impact
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

    @pytest.mark.parametrize(
        ("symbol", "expected_kind"),
        [
            pytest.param("Foo", "class", id="bare_class"),
            pytest.param("Foo.my_prop", "property", id="dotted_property"),
        ],
    )
    def test_impact_resolves_symbol_kind(
        self, tmp_path: Path, symbol: str, expected_kind: str
    ) -> None:
        """Bare class / dotted property resolve to a non-null definition.

        Verifies the expected kind is returned.
        """
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, symbol, project_root=tmp_path)
        assert result["definition"] is not None
        assert result["definition"]["kind"] == expected_kind

    def test_impact_dotted_nonexistent(self, tmp_path: Path) -> None:
        """Non-existent method returns definition=None without crashing."""
        pkg_dir = _make_dotted_project(tmp_path)
        result = analyze_impact(pkg_dir, "Foo.nonexistent", project_root=tmp_path)
        assert result["definition"] is None

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


class TestImpactTypeRefs:
    """AC2-3: analyze_impact includes type_refs and score considers them."""

    def test_impact_includes_type_refs(self, typed_pkg: object) -> None:
        """AC2: analyze_impact output has type_refs key."""
        from axm_ast.core.impact import analyze_impact

        result = analyze_impact(
            Path(typed_pkg.root),
            "MyModel",
        )
        assert "type_refs" in result
        assert len(result["type_refs"]) > 0

    def test_type_refs_modules_in_affected(
        self,
        typed_pkg: object,
    ) -> None:
        """Type ref modules are included in affected_modules."""
        from axm_ast.core.impact import analyze_impact

        result = analyze_impact(
            Path(typed_pkg.root),
            "MyModel",
        )
        type_ref_mods = {r["module"] for r in result["type_refs"]}
        for mod in type_ref_mods:
            assert mod in result["affected_modules"]


def _is_test_module_name(module: str) -> bool:
    """Local mirror of the public classification rule for assertion purposes.

    A module is a test module when any dotted segment starts with ``test_``
    or equals ``tests`` (see ``analyze_impact`` filter docs).
    """
    parts = module.split(".")
    return any(p.startswith("test_") or p == "tests" for p in parts)


def test_exclude_tests_filters_test_callers(tmp_path: Path) -> None:
    """Only prod callers remain when exclude_tests=True."""
    pkg_dir = _make_project_with_test_callers(tmp_path)
    result = analyze_impact(
        pkg_dir, "helper", project_root=tmp_path, exclude_tests=True
    )
    for caller in result["callers"]:
        assert not _is_test_module_name(caller["module"]), (
            f"Test caller not filtered: {caller['module']}"
        )
    # At least the cli caller should remain
    modules = [c["module"] for c in result["callers"]]
    assert any("cli" in m for m in modules)


def test_exclude_tests_false_keeps_all(tmp_path: Path) -> None:
    """Default (False) preserves all callers including tests."""
    pkg_dir = _make_project_with_test_callers(tmp_path)
    result = analyze_impact(
        pkg_dir, "helper", project_root=tmp_path, exclude_tests=False
    )
    modules = [c["module"] for c in result["callers"]]
    # Should include test callers
    assert any(_is_test_module_name(m) for m in modules)


def test_exclude_tests_filters_type_refs(tmp_path: Path) -> None:
    """Type refs from test modules are filtered."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "models.py").write_text(
        '"""Models."""\nclass MyModel:\n    """A model."""\n    pass\n'
    )
    (pkg / "cli.py").write_text(
        '"""CLI."""\ndef process(m: MyModel) -> None:\n    """Process."""\n    pass\n'
    )
    (pkg / "test_models.py").write_text(
        '"""Test models."""\n'
        "def check(m: MyModel) -> None:\n"
        '    """Check."""\n'
        "    pass\n"
    )
    result = analyze_impact(pkg, "MyModel", project_root=tmp_path, exclude_tests=True)
    for ref in result["type_refs"]:
        assert not _is_test_module_name(ref["module"]), (
            f"Test type ref not filtered: {ref['module']}"
        )


def test_impact_test_filter_none_excludes_tests(tmp_path: Path) -> None:
    """test_filter='none' removes all test callers from output."""
    pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
    result = analyze_impact(pkg, "target_fn", project_root=tmp_path, test_filter="none")
    # No callers from test modules
    for caller in result["callers"]:
        assert not _is_test_module_name(caller["module"]), (
            f"Test caller should be excluded: {caller['module']}"
        )
    # type_refs from test modules should also be excluded
    for ref in result.get("type_refs", []):
        assert not _is_test_module_name(ref["module"])


def test_impact_test_filter_all_includes_all(tmp_path: Path) -> None:
    """test_filter='all' keeps all callers including tests."""
    pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
    result = analyze_impact(pkg, "target_fn", project_root=tmp_path, test_filter="all")
    # Should have both prod and test callers
    modules = [c["module"] for c in result["callers"]]
    has_test = any(_is_test_module_name(m) for m in modules)
    has_prod = any(not _is_test_module_name(m) for m in modules)
    assert has_test, "test_filter='all' should include test callers"
    assert has_prod, "test_filter='all' should include prod callers"


def test_impact_test_filter_related_direct_only(tmp_path: Path) -> None:
    """test_filter='related' keeps only direct test callers.

    test_a calls target_fn directly -> included.
    test_b calls engine.run() (transitive) -> excluded.
    """
    pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
    result = analyze_impact(
        pkg, "target_fn", project_root=tmp_path, test_filter="related"
    )
    test_callers = [c for c in result["callers"] if _is_test_module_name(c["module"])]
    test_modules = {c["module"] for c in test_callers}
    # test_a calls target_fn directly -> included
    assert any("test_a" in m for m in test_modules), (
        "Direct test caller test_a should be included"
    )
    # test_b only calls engine.run -> excluded
    assert not any("test_b" in m for m in test_modules), (
        "Transitive test caller test_b should be excluded"
    )


class TestImpactTestFilterEdgeCases:
    """Edge cases for test_filter parameter."""

    def test_fundamental_type_related_filters_transitive(self, tmp_path: Path) -> None:
        """Symbol used in many tests but directly tested by few.

        FlowStep-like scenario: imported as a type in many test files
        but only directly exercised in a few.
        """
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "models.py").write_text(
            '"""Models."""\n'
            "class FlowStep:\n"
            '    """A flow step."""\n'
            "    def run(self) -> str:\n"
            '        """Run."""\n'
            '        return "ok"\n'
        )
        (pkg / "pipeline.py").write_text(
            '"""Pipeline."""\n'
            "def execute_pipeline() -> str:\n"
            '    """Execute."""\n'
            "    return FlowStep().run()\n"
        )
        # Direct test: exercises FlowStep directly (inside package)
        (pkg / "test_models.py").write_text(
            '"""Direct test of FlowStep."""\n'
            "def test_flowstep_run() -> None:\n"
            '    """Test."""\n'
            "    FlowStep()\n"
        )
        # Transitive tests: call pipeline, not FlowStep (inside package)
        tests = pkg / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text('"""Tests."""\n')
        for i in range(3):
            (tests / f"test_pipe_{i}.py").write_text(
                f'"""Pipeline test {i}."""\n'
                f"def test_pipeline_{i}() -> None:\n"
                '    """Test."""\n'
                "    execute_pipeline()\n"
            )

        result = analyze_impact(
            pkg, "FlowStep", project_root=tmp_path, test_filter="related"
        )
        test_callers = [
            c for c in result["callers"] if _is_test_module_name(c["module"])
        ]
        test_modules = {c["module"] for c in test_callers}
        # Only direct test (test_models) should be included
        assert any("test_models" in m for m in test_modules)
        # Transitive tests should not appear
        for m in test_modules:
            assert "test_pipe" not in m

    def test_no_test_callers_related_returns_empty(self, tmp_path: Path) -> None:
        """Symbol with zero test references -> related returns empty test section."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "core.py").write_text(
            '"""Core."""\n'
            "def internal_fn() -> int:\n"
            '    """No tests reference this."""\n'
            "    return 42\n"
        )
        (pkg / "api.py").write_text(
            '"""API."""\n'
            "def handler() -> int:\n"
            '    """Handler."""\n'
            "    return internal_fn()\n"
        )

        result = analyze_impact(
            pkg, "internal_fn", project_root=tmp_path, test_filter="related"
        )
        test_callers = [
            c for c in result["callers"] if _is_test_module_name(c["module"])
        ]
        assert test_callers == [], "No test callers should be present"

    def test_both_params_test_filter_takes_precedence(self, tmp_path: Path) -> None:
        """test_filter takes precedence over exclude_tests, with a warning."""
        pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = analyze_impact(
                pkg,
                "target_fn",
                project_root=tmp_path,
                exclude_tests=True,
                test_filter="all",
            )
            # test_filter="all" should win: test callers included
            test_callers = [
                c for c in result["callers"] if _is_test_module_name(c["module"])
            ]
            assert len(test_callers) > 0, (
                "test_filter='all' should include test callers "
                "even when exclude_tests=True"
            )
            # Should emit a warning about conflicting params
            assert any("test_filter" in str(warning.message) for warning in w), (
                "Should warn about conflicting exclude_tests and test_filter"
            )


def _import_tests(result: ImpactResult) -> list[str]:
    """Extract the ``test_files_by_import`` field with safe default."""
    return list(result.get("test_files_by_import", []))


def test_import_heuristic_fires(tmp_path: Path) -> None:
    """Heuristic finds test files importing the symbol's module."""
    pkg = _make_import_heuristic_project(tmp_path)
    # InternalCfg has no callers in the package, so map_tests won't find it
    # by name, but test_models.py imports mypkg.models -> heuristic fires.
    result = analyze_impact(pkg, "InternalCfg", project_root=tmp_path)
    assert "test_models.py" in _import_tests(result)


def test_import_heuristic_scoped_to_tests(tmp_path: Path) -> None:
    """Non-test files importing the module are not included."""
    pkg = _make_import_heuristic_project(tmp_path)
    result = analyze_impact(pkg, "InternalCfg", project_root=tmp_path)
    # helper_script.py is at project root, not in tests/ — must not leak in.
    assert "helper_script.py" not in _import_tests(result)


def test_no_tests_import_module(tmp_path: Path) -> None:
    """Completely untested module yields no ``test_files_by_import`` entry."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "orphan.py").write_text(
        '"""Orphan module."""\ndef nobody() -> None:\n    pass\n'
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_other.py").write_text(
        '"""Test other."""\ndef test_x() -> None:\n    assert True\n'
    )
    result = analyze_impact(pkg, "nobody", project_root=tmp_path)
    # The field is omitted when there are no matches.
    assert _import_tests(result) == []


def test_wildcard_import_detected(tmp_path: Path) -> None:
    """``from module import *`` is still detected by the import heuristic."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "utils.py").write_text('"""Utils."""\nclass UnreferencedHelper:\n    pass\n')
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_utils.py").write_text(
        '"""Test utils."""\nfrom mypkg.utils import *\n\n'
        "def test_u() -> None:\n    assert True\n"
    )
    # UnreferencedHelper is never named in test files (only the star import),
    # so map_tests cannot match — the heuristic must pick up test_utils.py.
    result = analyze_impact(pkg, "UnreferencedHelper", project_root=tmp_path)
    assert "test_utils.py" in _import_tests(result)
