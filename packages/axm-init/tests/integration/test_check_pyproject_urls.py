"""Split from ``test_pyproject_gold_standard_requirements.py``."""

from pathlib import Path

import pytest

from axm_init.checks.pyproject import check_pyproject_urls


class TestCheckPyprojectUrls:
    @pytest.mark.parametrize(
        ("use_gold", "expected"),
        [
            pytest.param(True, True, id="pass"),
            pytest.param(False, False, id="fail_missing_section"),
        ],
    )
    def test_urls(
        self,
        gold_project: Path,
        tmp_path: Path,
        use_gold: bool,
        expected: bool,
    ) -> None:
        if use_gold:
            project = gold_project
        else:
            (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
            project = tmp_path
        r = check_pyproject_urls(project)
        assert r.passed is expected

    def test_fail_partial_urls(self, tmp_path: Path) -> None:
        toml = '[project]\nname="x"\n[project.urls]\nHomepage = "h"\nRepository = "r"\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_urls(tmp_path)
        assert r.passed is False
        assert "Documentation" in str(r.details) or "Issues" in str(r.details)
