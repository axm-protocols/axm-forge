"""Tests for checks._workspace — workspace context detection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_init.checks._workspace import (
    ProjectContext,
    detect_context,
    find_workspace_root,
)

pytestmark = pytest.mark.integration

WORKSPACE_TOML = '[project]\nname = "ws"\n\n[tool.uv.workspace]\nmembers = ["*/*"]\n'
PAPER_TOML = '[project]\nname = "paper-x"\n\n[tool.axm-lab]\nslug = "paper-x"\n'


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(None, id="missing_pyproject"),
        pytest.param("{{invalid toml!!", id="corrupt_toml"),
    ],
)
def test_detect_context_falls_back_to_standalone(
    tmp_path: Path, content: str | None
) -> None:
    """Missing or corrupt pyproject.toml → STANDALONE (graceful fallback)."""
    if content is not None:
        (tmp_path / "pyproject.toml").write_text(content)
    assert detect_context(tmp_path) == ProjectContext.STANDALONE


def _make_workspace(root: Path) -> Path:
    """Materialise a uv workspace root holding one member package."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(WORKSPACE_TOML)
    member = root / "packages" / "pkg-a"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
    return root


def _make_member(root: Path) -> Path:
    """Materialise a plain member package inside a uv workspace."""
    return _make_workspace(root) / "packages" / "pkg-a"


def _make_paper_by_marker(root: Path) -> Path:
    """Materialise a paper declared by its axm-lab section, inside a workspace."""
    _make_workspace(root)
    paper = root / "papers" / "paper-x"
    paper.mkdir(parents=True)
    (paper / "pyproject.toml").write_text(PAPER_TOML)
    return paper


def _make_paper_by_structure(root: Path) -> Path:
    """Materialise a pyproject-less paper carrying the full structural triple."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "PLAN.md").write_text("# plan\n")
    (root / "paper").mkdir()
    (root / "experiments").mkdir()
    return root


def _make_near_miss(root: Path) -> Path:
    """Materialise a directory carrying only two of the three paper markers."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "PLAN.md").write_text("# plan\n")
    (root / "paper").mkdir()
    return root


def test_detect_context_reads_the_axm_lab_marker_inside_a_workspace(
    tmp_path: Path,
) -> None:
    """AC2: an axm-lab pyproject nested under a workspace root resolves to PAPER."""
    paper = _make_paper_by_marker(tmp_path / "ws")

    assert find_workspace_root(paper) is not None
    assert detect_context(paper) == ProjectContext.PAPER


def test_detect_context_reads_the_structural_triple_without_pyproject(
    tmp_path: Path,
) -> None:
    """AC3: PLAN markdown + paper/ + experiments/ resolves to PAPER."""
    paper = _make_paper_by_structure(tmp_path / "satellite")

    assert not (paper / "pyproject.toml").exists()
    assert detect_context(paper) == ProjectContext.PAPER


@pytest.mark.parametrize(
    ("builder", "expected"),
    [
        pytest.param(_make_paper_by_structure, "paper", id="paper"),
        pytest.param(_make_workspace, "workspace", id="workspace"),
        pytest.param(_make_member, "member", id="member"),
        pytest.param(_make_near_miss, "standalone", id="standalone_near_miss"),
    ],
)
def test_detect_context_resolves_the_four_contexts(
    tmp_path: Path,
    builder: Callable[[Path], Path],
    expected: str,
) -> None:
    """AC4: the four on-disk fixtures resolve to their respective contexts."""
    path = builder(tmp_path / expected)

    if expected == "member":
        assert find_workspace_root(path) is not None

    assert detect_context(path) == ProjectContext(expected)
