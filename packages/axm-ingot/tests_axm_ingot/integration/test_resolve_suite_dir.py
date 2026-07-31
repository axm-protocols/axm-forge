from __future__ import annotations

from pathlib import Path

import pytest

from axm_ingot.suite import resolve_suite_dir


@pytest.mark.integration
def test_resolve_suite_dir_prefers_namespaced_suite(tmp_path: Path) -> None:
    project = tmp_path / "axm-sample"
    canonical = project / "tests_axm_sample"
    legacy = project / "tests"
    canonical.mkdir(parents=True)
    legacy.mkdir()

    assert resolve_suite_dir(project) == canonical


@pytest.mark.integration
def test_resolve_suite_dir_falls_back_to_legacy_suite(tmp_path: Path) -> None:
    project = tmp_path / "axm-sample"
    legacy = project / "tests"
    legacy.mkdir(parents=True)

    assert resolve_suite_dir(project) == legacy


@pytest.mark.integration
def test_resolve_suite_dir_returns_none_without_suite(tmp_path: Path) -> None:
    project = tmp_path / "axm-sample"
    project.mkdir()

    assert resolve_suite_dir(project) is None
