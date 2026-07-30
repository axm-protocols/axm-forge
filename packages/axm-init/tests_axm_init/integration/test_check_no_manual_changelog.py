"""Tests for checks.changelog — gitcliff and manual changelog checks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_init.checks.changelog import check_no_manual_changelog


class TestCheckNoManualChangelog:
    @pytest.mark.parametrize(
        ("setup", "expected"),
        [
            pytest.param(None, True, id="pass-gold"),
            pytest.param(
                lambda p: (p / "CHANGELOG.md").write_text("# Changelog\n"),
                False,
                id="fail-has-changelog",
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
        r = check_no_manual_changelog(project)
        assert r.passed is expected
