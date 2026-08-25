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


def _manifest_files(directory: Path) -> list[Path]:
    """Return the manifest-looking files rendered inside *directory*."""
    return [
        p
        for p in directory.rglob("*")
        if p.is_file()
        and ("manifest" in p.name.lower() or p.suffix in {".toml", ".yaml", ".yml"})
    ]


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
    assert any(f.startswith("experiments") for f in files), files

    assert (tmp_path / "README.md").is_file()
    assert (tmp_path / "experiments").is_dir()
    sources = [
        p
        for p in tmp_path.iterdir()
        if p.is_file() and p.suffix in {".tex", ".md", ".qmd"} and p.name != "README.md"
    ]
    assert sources, sorted(p.name for p in tmp_path.iterdir())


def test_experiment_kind_scaffolds_indexed_dir_with_manifest(
    tmp_path: Path,
) -> None:
    """AC2: the experiment kind creates an indexed dir holding its manifest.

    A paper is scaffolded first; the experiment scaffold must then succeed and
    materialise a single indexed directory under ``experiments/`` carrying its
    manifest on disk.
    """
    assert _scaffold_paper(tmp_path).success is True

    result = _scaffold_experiment(tmp_path, "baseline")

    assert result.success is True, result.error
    exp_dirs = [d for d in (tmp_path / "experiments").iterdir() if d.is_dir()]
    assert len(exp_dirs) == 1, [d.name for d in exp_dirs]
    created = exp_dirs[0]
    assert created.name.startswith("01"), created.name
    assert _manifest_files(created), sorted(p.name for p in created.rglob("*"))


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
    assert "paper" in error, result.error
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_second_experiment_index_auto_increments(tmp_path: Path) -> None:
    """AC4: a paper already holding index 01 gets a directory named 02.

    The index is owned by the tool, not the template: scaffolding a second
    experiment must resolve the next free zero-padded index.
    """
    assert _scaffold_paper(tmp_path).success is True
    (tmp_path / "experiments" / "01-first").mkdir(parents=True, exist_ok=True)

    result = _scaffold_experiment(tmp_path, "second")

    assert result.success is True, result.error
    names = sorted(d.name for d in (tmp_path / "experiments").iterdir() if d.is_dir())
    assert any(n.startswith("02") for n in names), names
