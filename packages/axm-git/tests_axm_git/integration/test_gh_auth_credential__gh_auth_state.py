"""Integration contracts for the GitHub CLI credential declaration."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from axm_vault import AuthStatus, load_catalog

pytestmark = pytest.mark.integration


def _gh_auth_credential() -> object:
    contribution = importlib.import_module("axm_git.credentials").GH_AUTH_CREDENTIAL
    if not callable(contribution):
        return contribution
    return next(
        dependency
        for group in contribution()
        for dependency in group.auth_dependencies
        if dependency.name == "gh"
    )


def _write_gh_stub(directory: Path, returncode: int) -> None:
    executable = directory / "gh"
    executable.write_text(
        f"#!/bin/sh\nexit {returncode}\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)


def test_loaded_catalog_exposes_gh_auth_dependency() -> None:
    """AC3: The axm.credentials target resolves to the declaration object."""
    dependency_names = [
        dependency.name for dependency in load_catalog().auth_dependencies()
    ]

    assert "gh" in dependency_names


def test_declared_status_constates_all_gh_auth_states(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: Real gh stubs yield three distinct declared auth-state verdicts."""
    declaration = _gh_auth_credential()
    empty_path = tmp_path / "empty"
    empty_path.mkdir()
    monkeypatch.setenv("PATH", str(empty_path))
    observed = [declaration.status()]

    for returncode in (1, 0):
        stub_path = tmp_path / f"stub-{returncode}"
        stub_path.mkdir()
        _write_gh_stub(stub_path, returncode)
        monkeypatch.setenv("PATH", str(stub_path))
        observed.append(declaration.status())

    assert observed == [
        AuthStatus.TOOL_ABSENT,
        AuthStatus.DISCONNECTED,
        AuthStatus.CONNECTED,
    ]
    assert len(set(observed)) == 3


def test_loaded_catalog_has_no_gh_entry_point_rejection() -> None:
    """AC4: Catalog discovery records no rejection for the gh entry point."""
    rejected_entry_points = {
        rejection.entry_point for rejection in load_catalog().rejections()
    }

    assert "gh" not in rejected_entry_points
