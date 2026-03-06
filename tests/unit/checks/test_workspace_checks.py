"""Tests for workspace-specific checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.workspace import (
    check_matrix_packages,
    check_members_consistent,
    check_monorepo_plugin,
    check_packages_layout,
    check_pytest_importmode,
    check_pytest_testpaths,
    check_quality_workflow,
    check_requires_python_compat,
    check_root_name_collision,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def ws_root(tmp_path: Path) -> Path:
    """Minimal workspace root with one member under packages/."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    member = tmp_path / "packages" / "pkg-a"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\nrequires-python = ">=3.12"\n'
    )
    (member / "src").mkdir()
    (member / "tests").mkdir()
    return tmp_path


# ── check_packages_layout ────────────────────────────────────────────────────


class TestPackagesLayout:
    """Tests for check_packages_layout."""

    def test_valid(self, ws_root: Path) -> None:
        """Members under packages/ passes."""
        result = check_packages_layout(ws_root)
        assert result.passed
        assert result.weight == 3

    def test_no_members_passes(self, tmp_path: Path) -> None:
        """No members is valid (workspace just configured)."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        result = check_packages_layout(tmp_path)
        assert result.passed

    def test_members_outside_packages(self, tmp_path: Path) -> None:
        """Members not under packages/ fails."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["libs/*"]\n'
        )
        lib = tmp_path / "libs" / "pkg-a"
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        result = check_packages_layout(tmp_path)
        assert not result.passed
        assert "outside packages/" in result.message


# ── check_members_consistent ─────────────────────────────────────────────────


class TestMembersConsistent:
    """Tests for check_members_consistent."""

    def test_valid(self, ws_root: Path) -> None:
        """Member with pyproject.toml + src/ + tests/ passes."""
        result = check_members_consistent(ws_root)
        assert result.passed
        assert result.weight == 2

    def test_missing_tests(self, ws_root: Path) -> None:
        """Member missing tests/ fails with detail."""
        # Remove tests dir
        import shutil

        member = ws_root / "packages" / "pkg-a" / "tests"
        shutil.rmtree(member)
        result = check_members_consistent(ws_root)
        assert not result.passed
        assert any("tests/" in d for d in result.details)

    def test_no_members_passes(self, tmp_path: Path) -> None:
        """No members is valid (workspace just configured)."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        result = check_members_consistent(tmp_path)
        assert result.passed


# ── check_monorepo_plugin ────────────────────────────────────────────────────


class TestMonorepoPlugin:
    """Tests for check_monorepo_plugin."""

    def test_present(self, ws_root: Path) -> None:
        """mkdocs.yml with monorepo plugin passes."""
        (ws_root / "mkdocs.yml").write_text("plugins:\n  - monorepo\n  - search\n")
        result = check_monorepo_plugin(ws_root)
        assert result.passed

    def test_missing(self, ws_root: Path) -> None:
        """mkdocs.yml without monorepo fails."""
        (ws_root / "mkdocs.yml").write_text("plugins:\n  - search\n")
        result = check_monorepo_plugin(ws_root)
        assert not result.passed

    def test_no_mkdocs(self, ws_root: Path) -> None:
        """No mkdocs.yml fails."""
        result = check_monorepo_plugin(ws_root)
        assert not result.passed
        assert "not found" in result.message


# ── check_matrix_packages ────────────────────────────────────────────────────


class TestMatrixPackages:
    """Tests for check_matrix_packages."""

    def test_valid(self, ws_root: Path) -> None:
        """CI yml with --package passes."""
        ci = ws_root / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "ci.yml").write_text(
            "jobs:\n  test:\n    run: uv run pytest --package pkg-a\n"
        )
        result = check_matrix_packages(ws_root)
        assert result.passed

    def test_missing(self, ws_root: Path) -> None:
        """CI yml without --package fails."""
        ci = ws_root / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "ci.yml").write_text("jobs:\n  test:\n    run: pytest\n")
        result = check_matrix_packages(ws_root)
        assert not result.passed

    def test_no_ci(self, ws_root: Path) -> None:
        """No CI workflows fails gracefully."""
        result = check_matrix_packages(ws_root)
        assert not result.passed
        assert "not found" in result.message


# ── check_requires_python_compat ─────────────────────────────────────────────


class TestRequiresPythonCompat:
    """Tests for check_requires_python_compat."""

    def test_compatible(self, ws_root: Path) -> None:
        """All members >=3.12 passes."""
        result = check_requires_python_compat(ws_root)
        assert result.passed

    def test_conflict(self, ws_root: Path) -> None:
        """Different requires-python values fails."""
        pkg_b = ws_root / "packages" / "pkg-b"
        pkg_b.mkdir(parents=True)
        (pkg_b / "pyproject.toml").write_text(
            '[project]\nname = "pkg-b"\nrequires-python = ">=3.11,<3.12"\n'
        )
        result = check_requires_python_compat(ws_root)
        assert not result.passed
        assert "different" in result.message

    def test_no_requires_python(self, tmp_path: Path) -> None:
        """Members with no requires-python skipped."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        pkg = tmp_path / "packages" / "pkg-a"
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        result = check_requires_python_compat(tmp_path)
        assert result.passed
        assert "No requires-python" in result.message


# ── check_root_name_collision (AXM-313) ──────────────────────────────────────


class TestRootNameCollision:
    """Tests for check_root_name_collision."""

    def test_root_name_collision_detected(self, tmp_path: Path) -> None:
        """Root name == member name → fails."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "pkg-a"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        member = tmp_path / "packages" / "pkg-a"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        result = check_root_name_collision(tmp_path)
        assert not result.passed
        assert "collides" in result.message

    def test_root_name_collision_ok(self, ws_root: Path) -> None:
        """Root name differs from members → passes."""
        result = check_root_name_collision(ws_root)
        assert result.passed
        assert result.weight == 3

    def test_no_members_passes(self, tmp_path: Path) -> None:
        """No members is valid."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        result = check_root_name_collision(tmp_path)
        assert result.passed
        assert "No members" in result.message

    def test_case_insensitive_collision(self, tmp_path: Path) -> None:
        """Case-insensitive collision detected."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "My-App"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        member = tmp_path / "packages" / "my-app"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "my-app"\n')
        result = check_root_name_collision(tmp_path)
        assert not result.passed


# ── check_pytest_importmode (AXM-313) ────────────────────────────────────────


class TestPytestImportmode:
    """Tests for check_pytest_importmode."""

    def test_importmode_present(self, tmp_path: Path) -> None:
        """import_mode = 'importlib' passes."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            "[tool.pytest.ini_options]\n"
            'import_mode = "importlib"\n'
        )
        result = check_pytest_importmode(tmp_path)
        assert result.passed

    def test_importmode_missing(self, ws_root: Path) -> None:
        """No import_mode configuration → fails."""
        result = check_pytest_importmode(ws_root)
        assert not result.passed
        assert "importlib" in result.message


# ── check_pytest_testpaths (AXM-313) ─────────────────────────────────────────


class TestPytestTestpaths:
    """Tests for check_pytest_testpaths."""

    def test_testpaths_present(self, tmp_path: Path) -> None:
        """testpaths with member test dirs passes."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            "[tool.pytest.ini_options]\n"
            'testpaths = ["packages/pkg-a/tests"]\n'
        )
        result = check_pytest_testpaths(tmp_path)
        assert result.passed

    def test_testpaths_missing(self, ws_root: Path) -> None:
        """No testpaths configuration → fails."""
        result = check_pytest_testpaths(ws_root)
        assert not result.passed
        assert "testpaths" in result.message.lower()


# ── check_quality_workflow (AXM-313) ─────────────────────────────────────────


class TestQualityWorkflow:
    """Tests for check_quality_workflow."""

    def test_quality_workflow_present(self, ws_root: Path) -> None:
        """axm-quality.yml with audit + coverage passes."""
        ci = ws_root / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "axm-quality.yml").write_text(
            "name: axm-quality\njobs:\n  quality:\n"
            "    run: axm-audit\n    coverage: true\n"
        )
        result = check_quality_workflow(ws_root)
        assert result.passed

    def test_quality_workflow_missing(self, ws_root: Path) -> None:
        """No axm-quality.yml → fails."""
        result = check_quality_workflow(ws_root)
        assert not result.passed
        assert "not found" in result.message


# ── Auto-discovery and context gating ────────────────────────────────────────


class TestWorkspaceDiscovery:
    """Workspace checks are auto-discovered."""

    def test_workspace_category_discovered(self) -> None:
        """workspace category exists in ALL_CHECKS."""
        from axm_init.core.checker import ALL_CHECKS

        assert "workspace" in ALL_CHECKS
        assert len(ALL_CHECKS["workspace"]) == 9

    def test_standalone_skips_workspace(self, tmp_path: Path) -> None:
        """Standalone project doesn't get workspace checks."""
        from axm_init.core.checker import CheckEngine

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "solo"\n')
        engine = CheckEngine(tmp_path)
        result = engine.run()
        ws_checks = [c for c in result.checks if c.category == "workspace"]
        assert len(ws_checks) == 0
