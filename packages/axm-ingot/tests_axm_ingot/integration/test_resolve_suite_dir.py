from __future__ import annotations

from pathlib import Path

import pytest

from axm_ingot.suite import resolve_suite_dir, resolve_suite_dirs


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


def test_resolve_suite_dirs_includes_workspace_members(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "packages").mkdir(parents=True)
    (workspace / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    first = workspace / "packages" / "axm-first"
    second = workspace / "packages" / "axm-second"
    for member in (first, second):
        member.mkdir()
        (member / "pyproject.toml").write_text(
            f'[project]\nname = "{member.name}"\nversion = "0.1.0"\n'
        )
    first_suite = first / "tests_axm_first"
    second_suite = second / "tests"
    first_suite.mkdir()
    second_suite.mkdir()

    assert resolve_suite_dirs(workspace) == (first_suite, second_suite)
