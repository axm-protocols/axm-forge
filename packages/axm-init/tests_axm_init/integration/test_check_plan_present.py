"""Integration tests for the plan-document check (real filesystem)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.paper import _PLAN_FILENAME, check_plan_present

pytestmark = pytest.mark.integration


def test_plan_present_fails_when_missing_or_without_front_matter(
    tmp_path: Path,
) -> None:
    """AC2: a missing plan and a front-matter-less plan both fail."""
    missing = tmp_path / "missing"
    missing.mkdir()

    absent = check_plan_present(missing)

    assert absent.passed is False
    assert "PLAN.md" in f"{absent.message} {absent.fix}"

    prose = tmp_path / "prose"
    prose.mkdir()
    (prose / _PLAN_FILENAME).write_text("# Plan\n\nNo header at all.\n")

    headerless = check_plan_present(prose)

    assert headerless.passed is False
    assert "PLAN.md" in f"{headerless.message} {headerless.fix}"


def test_plan_present_passes_with_a_front_matter_block(tmp_path: Path) -> None:
    """AC2: a plan carrying a non-empty YAML front-matter block passes."""
    (tmp_path / _PLAN_FILENAME).write_text(
        "---\ntitle: Study plan\nstatus: draft\n---\n\n# Plan\n"
    )

    result = check_plan_present(tmp_path)

    assert result.passed is True
    assert "PLAN.md" in result.message
