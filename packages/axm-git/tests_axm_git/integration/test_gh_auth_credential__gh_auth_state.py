"""Integration contracts for the GitHub CLI credential declaration."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _gh_auth_credential() -> object:
    return importlib.import_module("axm_git.credentials").GH_AUTH_CREDENTIAL


def _write_gh_stub(directory: Path, returncode: int) -> None:
    executable = directory / "gh"
    executable.write_text(
        f"#!/bin/sh\nexit {returncode}\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)


def test_pyproject_entry_point_resolves_to_gh_auth_declaration() -> None:
    """AC3: The axm.credentials target resolves to the declaration object."""
    project_root = Path(__file__).parents[2]
    with (project_root / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)

    targets = pyproject["project"]["entry-points"]["axm.credentials"].values()
    target = "axm_git.credentials:GH_AUTH_CREDENTIAL"
    assert target in targets

    module_name, attribute_name = target.split(":", maxsplit=1)
    resolved = getattr(importlib.import_module(module_name), attribute_name)
    assert resolved is _gh_auth_credential()


def test_declared_check_constates_all_gh_auth_states(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: Real gh stubs yield three distinct declared auth-state verdicts."""
    declaration = _gh_auth_credential()
    empty_path = tmp_path / "empty"
    empty_path.mkdir()
    monkeypatch.setenv("PATH", str(empty_path))
    observed = [declaration.check()]

    for returncode in (1, 0):
        stub_path = tmp_path / f"stub-{returncode}"
        stub_path.mkdir()
        _write_gh_stub(stub_path, returncode)
        monkeypatch.setenv("PATH", str(stub_path))
        observed.append(declaration.check())

    assert observed == ["not_installed", "logged_out", "logged_in"]
    assert len(set(observed)) == 3
