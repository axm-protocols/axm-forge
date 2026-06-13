"""Split from ``test_pyproject_gold_standard_requirements.py``."""

from pathlib import Path

import pytest

from axm_init.checks.pyproject import check_pyproject_ruff
from tests.integration._helpers import _write_toml


class TestCheckPyprojectRuff:
    @pytest.mark.parametrize(
        ("use_gold", "expected"),
        [
            pytest.param(True, True, id="pass"),
            pytest.param(False, False, id="fail_no_per_file_ignores"),
        ],
    )
    def test_ruff_config(
        self,
        gold_project: Path,
        tmp_path: Path,
        use_gold: bool,
        expected: bool,
    ) -> None:
        if use_gold:
            project = gold_project
        else:
            (tmp_path / "pyproject.toml").write_text(
                '[project]\nname="x"\n[tool.ruff.lint]\nselect=["E"]\n'
            )
            project = tmp_path
        r = check_pyproject_ruff(project)
        assert r.passed is expected


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
