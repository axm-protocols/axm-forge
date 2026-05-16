"""Split from ``test_src_layout_and_repo_files.py``."""

from pathlib import Path

from axm_init.checks.structure import check_license_file


class TestCheckLicenseFile:
    def test_pass(self, gold_project: Path) -> None:
        r = check_license_file(gold_project)
        assert r.passed is True

    def test_fail(self, empty_project: Path) -> None:
        r = check_license_file(empty_project)
        assert r.passed is False
