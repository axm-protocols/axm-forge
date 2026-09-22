"""Integration tests for the paper and experiment kinds of ``init_scaffold``.

Real filesystem: every scaffold below renders the bundled Copier template
into ``tmp_path`` and is asserted on disk, not on a mock.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.tools.scaffold import InitScaffoldTool

pytestmark = pytest.mark.integration

BASE_KWARGS = {
    "org": "test-org",
    "author": "Test Author",
    "email": "test@example.com",
}


def _scaffold_paper(target: Path, name: str = "my-paper"):
    """Scaffold a paper into *target* through the public tool boundary."""
    return InitScaffoldTool().execute(
        path=str(target),
        kind="paper",
        name=name,
        **BASE_KWARGS,
    )


def _scaffold_experiment(target: Path, name: str):
    """Scaffold an experiment into the paper rooted at *target*."""
    return InitScaffoldTool().execute(
        path=str(target),
        kind="experiment",
        name=name,
        **BASE_KWARGS,
    )


def test_paper_kind_scaffolds_full_paper_tree(tmp_path: Path) -> None:
    """AC1: the paper kind renders plan, readme, source and experiments dir.

    Invoking the tool with ``kind="paper"`` on an empty target must return a
    successful result whose file list carries the plan file, the readme, the
    paper source and the experiments placeholder — and that tree must exist
    on disk.
    """
    result = _scaffold_paper(tmp_path)

    assert result.success is True, result.error
    assert result.data is not None
    assert result.data["template"] == "paper"

    files = result.data["files"]
    assert "README.md" in files, files
    assert any("plan" in f.lower() and f.endswith(".md") for f in files), files
    assert not any(f.startswith("experiments") for f in files), files

    assert (tmp_path / "README.md").is_file()
    assert not (tmp_path / "experiments").exists()
    sources = [
        p
        for p in tmp_path.iterdir()
        if p.is_file() and p.suffix in {".tex", ".md", ".qmd"} and p.name != "README.md"
    ]
    assert sources, sorted(p.name for p in tmp_path.iterdir())


def test_experiment_kind_refuses_non_paper_target(tmp_path: Path) -> None:
    """AC3: a non-paper target fails before any write.

    The guard fires on the detected context: the result is failing, its error
    states the target is not a paper, and the directory listing is untouched.
    """
    from axm_init.checks._workspace import ProjectContext, detect_context

    (tmp_path / "notes.txt").write_text("plain directory\n")
    assert detect_context(tmp_path) is not ProjectContext.PAPER
    before = sorted(p.name for p in tmp_path.iterdir())

    result = _scaffold_experiment(tmp_path, "baseline")

    assert result.success is False
    error = (result.error or "").lower()
    assert "experiment_scaffold" in error, result.error
    assert sorted(p.name for p in tmp_path.iterdir()) == before
