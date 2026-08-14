"""Integration: the paper structure check on its conditional entries.

Real filesystem: every test lays out a paper root under ``tmp_path``.

Two entries of the topology are conditional, so a flat "require them all" rule
would be wrong in both directions:

``INDEX.md`` is GENERATED from the experiment manifests, never written by hand.
A paper that has no experiment yet legitimately carries none — but a paper whose
``experiments/`` holds experiment folders and still has no index means the
registry was never produced, which is exactly the state this check should name.

``data/`` is the cohort SHARED between experiments. A paper whose experiments
each carry their own inputs has no shared cohort and needs no ``data/``; but a
paper that ships one must document its provenance in ``PIPELINE.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.paper import check_paper_structure
from axm_init.models.check import CheckResult

pytestmark = pytest.mark.integration


def _blob(result: CheckResult) -> str:
    """Flatten message and details into one lowercase searchable string."""
    return f"{result.message} {' '.join(result.details)}".lower()


def _paper_root(path: Path) -> Path:
    """Lay out the unconditional entries of a paper root."""
    (path / "paper").mkdir()
    (path / "experiments").mkdir()
    (path / "README.md").write_text("# Paper\n", encoding="utf-8")
    (path / "PIPELINE.md").write_text("# Pipeline\n", encoding="utf-8")
    return path


def _experiment(root: Path, name: str) -> None:
    """Add one experiment folder carrying a manifest to *root*."""
    folder = root / "experiments" / name
    folder.mkdir(parents=True)
    (folder / "manifest.yaml").write_text(
        f'contract_version: "1.0.0"\nid: "{name}"\n', encoding="utf-8"
    )


def test_a_paper_with_no_experiment_needs_no_index(tmp_path: Path) -> None:
    """An empty experiments/ carries no index: there is nothing to register."""
    result = check_paper_structure(_paper_root(tmp_path))

    assert result.passed is True, _blob(result)


def test_a_paper_with_experiments_and_no_index_is_named(tmp_path: Path) -> None:
    """Experiments present but no INDEX.md: the registry was never generated."""
    root = _paper_root(tmp_path)
    _experiment(root, "01-first")

    result = check_paper_structure(root)

    assert result.passed is False
    assert "index.md" in _blob(result)
    # The registry is generated, so the fix names the generator rather than
    # telling the author to create the file by hand.
    assert "experiment_index" in result.fix


def test_a_paper_with_experiments_and_an_index_passes(tmp_path: Path) -> None:
    """The generated registry satisfies the conditional entry."""
    root = _paper_root(tmp_path)
    _experiment(root, "01-first")
    (root / "INDEX.md").write_text("| id |\n", encoding="utf-8")

    result = check_paper_structure(root)

    assert result.passed is True, _blob(result)


def test_a_folder_without_a_manifest_is_not_an_experiment(tmp_path: Path) -> None:
    """A stray directory under experiments/ does not trigger the index rule.

    ``experiments/`` legitimately holds folders that are not experiments (a
    meta-study, scratch material). Only a folder carrying a manifest counts,
    so a paper holding just those still needs no generated registry.
    """
    root = _paper_root(tmp_path)
    (root / "experiments" / "skills-zero").mkdir()

    result = check_paper_structure(root)

    assert result.passed is True, _blob(result)
