"""Integration tests for the paper structure check (real filesystem)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.paper import check_paper_structure
from axm_init.models.check import CheckResult

pytestmark = pytest.mark.integration


def _blob(result: CheckResult) -> str:
    """Flatten message and details into one lowercase searchable string."""
    return f"{result.message} {' '.join(result.details)}".lower()


def test_paper_structure_fails_and_names_the_missing_directories(
    tmp_path: Path,
) -> None:
    """AC1: paper/ and experiments/ absent -> failed result naming both."""
    (tmp_path / "README.md").write_text("# Paper\n")

    result = check_paper_structure(tmp_path)

    assert result.passed is False
    blob = _blob(result)
    assert "paper" in blob
    assert "experiments" in blob


def test_paper_structure_fails_and_names_the_missing_readme(tmp_path: Path) -> None:
    """AC1: the readme is part of the named missing entries too."""
    (tmp_path / "paper").mkdir()
    (tmp_path / "experiments").mkdir()

    result = check_paper_structure(tmp_path)

    assert result.passed is False
    assert "readme" in _blob(result)


def test_paper_structure_passes_on_a_complete_tree(tmp_path: Path) -> None:
    """AC1: paper/, experiments/ and the readme all present -> passed result."""
    (tmp_path / "paper").mkdir()
    (tmp_path / "experiments").mkdir()
    (tmp_path / "README.md").write_text("# Paper\n")
    (tmp_path / "PIPELINE.md").write_text("# Pipeline\n")

    result = check_paper_structure(tmp_path)

    assert result.passed is True


def test_paper_structure_fails_and_names_the_provenance_document(
    tmp_path: Path,
) -> None:
    # AC1: an otherwise complete paper root missing the provenance document
    # fails, and both the message and the fix name PIPELINE.md.
    (tmp_path / "paper").mkdir()
    (tmp_path / "experiments").mkdir()
    (tmp_path / "README.md").write_text("# Paper\n")

    result = check_paper_structure(tmp_path)

    assert result.passed is False
    assert "PIPELINE.md" in f"{result.message} {result.fix}"
