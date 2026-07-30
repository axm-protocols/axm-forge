"""Unit tests for ``check_tests_dir`` (relocated from integration)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.structure import check_tests_dir


class TestCheckTestsDirPyramid:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("empty_project", False, id="fail"),
        ],
    )
    def test_tests_dir(
        self,
        request: pytest.FixtureRequest,
        fixture_name: str,
        expected: bool,
    ) -> None:
        project: Path = request.getfixturevalue(fixture_name)
        r = check_tests_dir(project)
        assert r.passed is expected
