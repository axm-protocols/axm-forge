"""Split from ``test_diataxis_docs_layout_requirements.py``."""

from pathlib import Path

from axm_init.checks.docs import check_readme


class TestCheckReadme:
    def test_pass(self, gold_project: Path) -> None:
        r = check_readme(gold_project)
        assert r.passed is True

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_readme(empty_project)
        assert r.passed is False

    def test_fail_no_features(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# test\n## Installation\n")
        r = check_readme(tmp_path)
        assert r.passed is False
