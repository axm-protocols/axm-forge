"""Split from ``test_precommit_and_makefile_tooling.py``."""

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_init.checks.tooling import check_precommit_conventional


class TestCheckPrecommitConventional:
    @pytest.mark.parametrize(
        ("setup", "expected"),
        [
            pytest.param(None, True, id="pass-gold"),
            pytest.param(
                lambda p: (p / ".pre-commit-config.yaml").write_text(
                    "repos:\n  - repo: x\n"
                ),
                False,
                id="fail-no-hook",
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
        r = check_precommit_conventional(project)
        assert r.passed is expected
