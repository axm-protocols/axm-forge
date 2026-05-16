"""Split from ``test_pyproject_gold_standard_requirements.py``."""

from pathlib import Path

from axm_init.checks.pyproject import check_pyproject_coverage


class TestCheckPyprojectCoverage:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_coverage(gold_project)
        assert r.passed is True

    def test_fail_missing(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_pyproject_coverage(tmp_path)
        assert r.passed is False
