"""Split from ``test_dependency_hygiene_dev_and_docs.py``."""

from pathlib import Path

from axm_init.checks.deps import check_dev_deps


class TestCheckDevDeps:
    def test_pass(self, gold_project: Path) -> None:
        r = check_dev_deps(gold_project)
        assert r.passed is True

    def test_fail_no_pyproject(self, empty_project: Path) -> None:
        r = check_dev_deps(empty_project)
        assert r.passed is False

    def test_fail_missing_deps(self, tmp_path: Path) -> None:
        toml = '[project]\nname="x"\n[dependency-groups]\ndev = ["pytest"]\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_dev_deps(tmp_path)
        assert r.passed is False
