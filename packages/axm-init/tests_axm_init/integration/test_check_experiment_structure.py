"""Integration tests for the experiment form checks on real folders."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.experiment import (
    check_experiment_files,
    check_experiment_structure,
)

pytestmark = pytest.mark.integration

_REQUIRED_DIRS = ("inputs", "scripts", "outputs", "analysis", "figures")


def _make_dirs(root: Path, names: tuple[str, ...]) -> None:
    """Create *names* as directories under *root*."""
    for name in names:
        (root / name).mkdir(parents=True, exist_ok=True)


def test_structure_check_passes_on_a_complete_experiment_folder(
    tmp_path: Path,
) -> None:
    """AC1: the five required directories make the shape check pass."""
    _make_dirs(tmp_path, _REQUIRED_DIRS)

    result = check_experiment_structure(tmp_path)

    assert result.passed is True
    assert result.category == "experiment"


def test_structure_check_names_exactly_the_missing_directories(
    tmp_path: Path,
) -> None:
    """AC1: a failing result names the missing directories and only those."""
    _make_dirs(tmp_path, ("inputs", "scripts"))

    result = check_experiment_structure(tmp_path)

    assert result.passed is False
    for missing in ("outputs", "analysis", "figures"):
        assert missing in result.message
    for present in ("inputs", "scripts"):
        assert present not in result.message


def test_files_check_fails_when_the_readme_is_absent(tmp_path: Path) -> None:
    """AC2: a missing README.md fails the root-files check by name."""
    (tmp_path / "manifest.yaml").write_text("id: demo\n", encoding="utf-8")

    result = check_experiment_files(tmp_path)

    assert result.passed is False
    assert "README.md" in result.message
    assert "manifest.yaml" not in result.message


def test_files_check_passes_when_both_root_files_exist(tmp_path: Path) -> None:
    """AC2: manifest.yaml + README.md at the root pass the root-files check."""
    (tmp_path / "manifest.yaml").write_text("id: demo\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")

    result = check_experiment_files(tmp_path)

    assert result.passed is True
    assert result.category == "experiment"


def test_todo_valued_manifest_still_passes_both_form_checks(tmp_path: Path) -> None:
    """AC4: neither check reads the manifest CONTENT — TODO values pass."""
    _make_dirs(tmp_path, _REQUIRED_DIRS)
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    (tmp_path / "manifest.yaml").write_text(
        "contract_version: TODO\nid: TODO\n", encoding="utf-8"
    )

    structure = check_experiment_structure(tmp_path)
    files = check_experiment_files(tmp_path)

    assert structure.passed is True
    assert files.passed is True
