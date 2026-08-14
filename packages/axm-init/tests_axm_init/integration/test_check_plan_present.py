"""Integration tests for the plan-document check (real filesystem)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.paper import check_plan_present

pytestmark = pytest.mark.integration


def test_plan_present_fails_when_missing_or_without_front_matter(
    tmp_path: Path,
) -> None:
    """AC2: a missing plan and a front-matter-less plan both fail."""
    missing = tmp_path / "missing"
    missing.mkdir()

    assert check_plan_present(missing).passed is False

    prose = tmp_path / "prose"
    prose.mkdir()
    (prose / "plan.md").write_text("# Plan\n\nNo header at all.\n")

    assert check_plan_present(prose).passed is False


def test_plan_present_passes_with_a_front_matter_block(tmp_path: Path) -> None:
    """AC2: a plan carrying a non-empty YAML front-matter block passes."""
    (tmp_path / "plan.md").write_text(
        "---\ntitle: Study plan\nstatus: draft\n---\n\n# Plan\n"
    )

    result = check_plan_present(tmp_path)

    assert result.passed is True
