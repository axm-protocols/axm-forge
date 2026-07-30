"""Split from ``test_pyproject_gold_standard_requirements.py``."""

from pathlib import Path

from axm_init.checks.pyproject import check_pyproject_exists


class TestCheckPyprojectExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_exists(gold_project)
        assert r.passed is True
        assert r.weight == 4

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_pyproject_exists(empty_project)
        assert r.passed is False
        assert r.fix != ""

    def test_fail_corrupt(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("{{invalid toml")
        r = check_pyproject_exists(tmp_path)
        assert r.passed is False
        assert "unparsable" in r.message.lower() or "parse" in r.message.lower()
