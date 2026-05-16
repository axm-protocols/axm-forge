"""Split from ``test_pyproject_gold_standard_requirements.py``."""

from pathlib import Path

from axm_init.checks.pyproject import check_pyproject_ruff
from tests.integration._helpers import _write_toml


class TestCheckPyprojectRuff:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_ruff(gold_project)
        assert r.passed is True

    def test_fail_no_per_file_ignores(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname="x"\n[tool.ruff.lint]\nselect=["E"]\n'
        )
        r = check_pyproject_ruff(tmp_path)
        assert r.passed is False


class TestStandaloneNoFallback:
    """test_standalone_no_fallback.

    Standalone project with no ruff config still fails.
    """

    def test_fails_without_workspace(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path / "pyproject.toml",
            """\
            [project]
            name = "standalone"
            version = "0.1.0"
            """,
        )
        result = check_pyproject_ruff(tmp_path)
        assert not result.passed


class TestWorkspaceRootNoPyproject:
    """Edge: workspace root dir exists but has no pyproject.toml."""

    def test_falls_back_to_member_only(self, tmp_path: Path) -> None:
        """When no workspace root pyproject.toml exists, use member config only."""
        member = tmp_path / "packages" / "pkg"
        member.mkdir(parents=True, exist_ok=True)
        _write_toml(
            member / "pyproject.toml",
            """\
            [project]
            name = "pkg"
            version = "0.1.0"
            """,
        )
        # No workspace root pyproject.toml at all
        result = check_pyproject_ruff(member)
        assert not result.passed  # No ruff config anywhere -> fail
