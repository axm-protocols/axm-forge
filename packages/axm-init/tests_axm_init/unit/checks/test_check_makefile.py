"""Unit tests for ``check_makefile`` (relocated from integration)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.tooling import check_makefile


class TestCheckMakefile:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("empty_project", False, id="fail_missing"),
        ],
    )
    def test_passed(
        self, request: pytest.FixtureRequest, fixture_name: str, expected: bool
    ) -> None:
        project: Path = request.getfixturevalue(fixture_name)
        r = check_makefile(project)
        assert r.passed is expected
