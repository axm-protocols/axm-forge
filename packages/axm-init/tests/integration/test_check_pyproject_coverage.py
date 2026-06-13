"""Split from ``test_pyproject_gold_standard_requirements.py``."""

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_init.checks.pyproject import check_pyproject_coverage


class TestCheckPyprojectCoverage:
    @pytest.mark.parametrize(
        ("setup", "expected"),
        [
            pytest.param(None, True, id="pass-gold"),
            pytest.param(
                lambda p: (p / "pyproject.toml").write_text('[project]\nname="x"\n'),
                False,
                id="fail-missing",
            ),
        ],
    )
    def test_passed(
        self,
        setup: Callable[[Path], object] | None,
        expected: bool,
        gold_project: Path,
        tmp_path: Path,
    ) -> None:
        project = gold_project
        if setup is not None:
            setup(tmp_path)
            project = tmp_path
        r = check_pyproject_coverage(project)
        assert r.passed is expected
