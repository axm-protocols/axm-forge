"""Split from ``test_pyproject_gold_standard_requirements.py``."""

from pathlib import Path

from axm_init.checks.pyproject import check_pyproject_classifiers


class TestCheckPyprojectClassifiers:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_classifiers(gold_project)
        assert r.passed is True
        assert r.weight == 1

    def test_fail_no_classifiers(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        r = check_pyproject_classifiers(tmp_path)
        assert r.passed is False

    def test_fail_missing_typed(self, tmp_path: Path) -> None:
        toml = (
            '[project]\nname="x"\nclassifiers = ['
            '"Development Status :: 3 - Alpha",'
            '"Programming Language :: Python :: 3.12"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_classifiers(tmp_path)
        assert r.passed is False
        assert "Typed" in str(r.details)
