"""Split from ``test_impact.py``."""

from pathlib import Path

from axm_ast.core.impact import map_tests


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


class TestMapTests:
    """Test test file detection."""

    def test_finds_relevant_tests(self, tmp_path: Path) -> None:
        """Identifies test files that reference the symbol."""
        _make_project(tmp_path)
        test_files = map_tests("helper", tmp_path)
        names = [t.name for t in test_files]
        assert "test_core.py" in names

    def test_no_tests_dir(self, tmp_path: Path) -> None:
        """Graceful when no tests/ exists."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        test_files = map_tests("helper", tmp_path)
        assert test_files == []

    def test_finds_tests_in_pyramid_subdirs(self, tmp_path: Path) -> None:
        """AXM pyramid layout (tests/unit/…) is scanned recursively.

        Regression guard: a flat ``glob`` misses ``tests/unit|integration``
        entirely, so ``map_tests`` returned ``[]`` on every AXM package.
        """
        tests = tmp_path / "tests" / "unit" / "core"
        tests.mkdir(parents=True)
        (tests / "test_helper.py").write_text(
            "def test_helper() -> None:\n    helper(1)\n"
        )
        test_files = map_tests("helper", tmp_path)
        assert [t.name for t in test_files] == ["test_helper.py"]

    def test_finds_tests_in_namespaced_suite(self, tmp_path: Path) -> None:
        """Migrated tests_<pkg>/ suites participate in impact analysis."""
        project = tmp_path / "axm-sample"
        tests = project / "tests_axm_sample" / "unit" / "core"
        tests.mkdir(parents=True)
        (tests / "test_helper.py").write_text(
            "def test_helper() -> None:\n    helper(1)\n"
        )

        test_files = map_tests("helper", project)

        assert [t.name for t in test_files] == ["test_helper.py"]

    def test_finds_tests_in_workspace_member_suites(self, tmp_path: Path) -> None:
        """Workspace impact scans every resolved member suite."""
        workspace = tmp_path / "workspace"
        (workspace / "packages").mkdir(parents=True)
        (workspace / "pyproject.toml").write_text(
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        first = workspace / "packages" / "axm-first"
        second = workspace / "packages" / "axm-second"
        for member in (first, second):
            member.mkdir()
            (member / "pyproject.toml").write_text(
                f'[project]\nname = "{member.name}"\nversion = "0.1.0"\n'
            )
        first_test = first / "tests_axm_first" / "unit" / "test_helper.py"
        second_test = second / "tests_axm_second" / "unit" / "test_other.py"
        first_test.parent.mkdir(parents=True)
        second_test.parent.mkdir(parents=True)
        first_test.write_text("def test_helper() -> None:\n    helper(1)\n")
        second_test.write_text("def test_other() -> None:\n    helper(2)\n")

        test_files = map_tests("helper", workspace)

        assert test_files == [first_test, second_test]
