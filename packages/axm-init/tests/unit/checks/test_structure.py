"""Tests for checks.structure — project structure checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.structure import (
    check_contributing,
    check_license_file,
    check_py_typed,
    check_python_version,
    check_src_layout,
    check_tests_dir,
    check_uv_lock,
)


class TestCheckSrcLayout:
    def test_pass(self, gold_project: Path) -> None:
        r = check_src_layout(gold_project)
        assert r.passed is True

    def test_fail_no_src(self, empty_project: Path) -> None:
        r = check_src_layout(empty_project)
        assert r.passed is False

    def test_fail_flat_layout(self, tmp_path: Path) -> None:
        pkg = tmp_path / "my_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        r = check_src_layout(tmp_path)
        assert r.passed is False


class TestCheckPyTyped:
    def test_pass(self, gold_project: Path) -> None:
        r = check_py_typed(gold_project)
        assert r.passed is True

    def test_fail(self, tmp_path: Path) -> None:
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        r = check_py_typed(tmp_path)
        assert r.passed is False


class TestCheckTestsDir:
    def test_pass(self, gold_project: Path) -> None:
        r = check_tests_dir(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_tests_dir(empty_project)
        assert r.passed is False


class TestCheckContributing:
    def test_pass(self, gold_project: Path) -> None:
        r = check_contributing(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_contributing(empty_project)
        assert r.passed is False


class TestCheckLicenseFile:
    def test_pass(self, gold_project: Path) -> None:
        r = check_license_file(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_license_file(empty_project)
        assert r.passed is False


class TestCheckUvLock:
    def test_pass(self, gold_project: Path) -> None:
        r = check_uv_lock(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_uv_lock(empty_project)
        assert r.passed is False

    def test_pass_workspace_root(self, tmp_path: Path) -> None:
        """uv.lock at workspace root is detected for a member package."""
        # Workspace root
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n\n[tool.uv.workspace]\nmembers = ["pkg"]\n'
        )
        (tmp_path / "uv.lock").write_text("version = 1\n")
        # Member package (no local uv.lock)
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        r = check_uv_lock(pkg)
        assert r.passed is True
        assert "workspace root" in r.message

    def test_fail_workspace_no_lock(self, tmp_path: Path) -> None:
        """Workspace root exists but has no uv.lock -> fail."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n\n[tool.uv.workspace]\nmembers = ["pkg"]\n'
        )
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        r = check_uv_lock(pkg)
        assert r.passed is False


class TestCheckPythonVersion:
    def test_pass(self, gold_project: Path) -> None:
        r = check_python_version(gold_project)
        assert r.passed is True
        assert r.weight == 1

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_python_version(empty_project)
        assert r.passed is False
