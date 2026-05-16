"""Split from ``test_src_layout_and_repo_files.py``."""

from pathlib import Path

from axm_init.checks.structure import check_python_version


class TestCheckPythonVersion:
    def test_pass(self, gold_project: Path) -> None:
        r = check_python_version(gold_project)
        assert r.passed is True
        assert r.weight == 1

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_python_version(empty_project)
        assert r.passed is False
