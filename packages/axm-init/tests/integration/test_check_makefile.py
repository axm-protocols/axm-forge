"""Split from ``test_precommit_and_makefile_tooling.py``."""

from pathlib import Path

from axm_init.checks.tooling import check_makefile


class TestCheckMakefile:
    def test_pass(self, gold_project: Path) -> None:
        r = check_makefile(gold_project)
        assert r.passed is True

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_makefile(empty_project)
        assert r.passed is False

    def test_fail_partial_targets(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("install:\n\techo hi\n")
        r = check_makefile(tmp_path)
        assert r.passed is False
        assert len(r.details) > 0  # reports missing targets
