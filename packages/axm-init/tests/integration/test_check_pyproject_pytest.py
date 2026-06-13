"""Split from ``test_pyproject_gold_standard_requirements.py``."""

from pathlib import Path

import pytest

from axm_init.checks.pyproject import check_pyproject_pytest


class TestCheckPyprojectPytest:
    @pytest.mark.parametrize(
        ("use_gold", "expected"),
        [
            pytest.param(True, True, id="pass"),
            pytest.param(False, False, id="fail_missing"),
        ],
    )
    def test_pytest_config(
        self,
        gold_project: Path,
        tmp_path: Path,
        use_gold: bool,
        expected: bool,
    ) -> None:
        if use_gold:
            project = gold_project
        else:
            (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
            project = tmp_path
        r = check_pyproject_pytest(project)
        assert r.passed is expected
