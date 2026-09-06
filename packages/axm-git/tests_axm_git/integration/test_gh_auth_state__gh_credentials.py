"""Integration contracts for installed GitHub credential discovery."""

from __future__ import annotations

import subprocess
import tomllib
from collections.abc import Iterator
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path

import pytest
from axm_vault import AuthDependencySpec, AuthStatus, load_catalog
from axm_vault import catalog as catalog_module
from pytest_mock import MockerFixture

from axm_git.core import gh_auth as gh_auth_module

pytestmark = pytest.mark.integration


def _configured_gh_entry_point() -> EntryPoint:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    configuration = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    target = configuration["project"]["entry-points"]["axm.credentials"]["gh"]
    return EntryPoint(name="gh", value=target, group="axm.credentials")


@pytest.fixture(autouse=True)
def _fresh_credential_catalog(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    installed = [
        endpoint
        for endpoint in entry_points(group="axm.credentials")
        if endpoint.name != "gh"
    ]
    configured = _configured_gh_entry_point()
    monkeypatch.setattr(
        catalog_module,
        "entry_points",
        lambda *, group: [*installed, configured] if group == "axm.credentials" else [],
    )
    load_catalog.cache_clear()
    yield
    load_catalog.cache_clear()


def _loaded_gh_dependency() -> AuthDependencySpec:
    dependency = next(
        (
            candidate
            for candidate in load_catalog().auth_dependencies()
            if candidate.name == "gh"
        ),
        None,
    )
    assert dependency is not None
    return dependency


def _assert_direct_callable_target() -> None:
    assert _configured_gh_entry_point().value == "axm_git.credentials:gh_credentials"


def _completed_gh_auth(returncode: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["gh", "auth", "status"],
        returncode=returncode,
        stdout="",
        stderr="",
    )


def test_loaded_catalog_enumerates_gh_auth_dependency() -> None:
    """AC1: A cold catalog load enumerates the GitHub CLI auth dependency."""
    dependency_names = {
        dependency.name for dependency in load_catalog().auth_dependencies()
    }

    assert "gh" in dependency_names
    _assert_direct_callable_target()


def test_loaded_catalog_preserves_other_auth_dependencies() -> None:
    """AC2: Adding GitHub preserves every conforming installed contribution."""
    other_groups = [
        group
        for endpoint in entry_points(group="axm.credentials")
        if endpoint.name != "gh"
        for group in endpoint.load()()
    ]
    expected_dependencies = {
        (group.id, dependency.name)
        for group in other_groups
        for dependency in group.auth_dependencies
    }
    expected_dependencies.add(("gh", "gh"))

    catalog_dependencies = {
        (group.id, dependency.name)
        for group in load_catalog().groups()
        for dependency in group.auth_dependencies
    }

    assert expected_dependencies <= catalog_dependencies
    _assert_direct_callable_target()


def test_loaded_gh_dependency_reports_connected(mocker: MockerFixture) -> None:
    """AC3: The catalog dependency reports a posed open session as connected."""
    dependency = _loaded_gh_dependency()
    mocker.patch.object(gh_auth_module, "gh_available", return_value=False)
    mocker.patch.object(
        gh_auth_module,
        "run_gh",
        return_value=_completed_gh_auth(returncode=0),
    )

    assert dependency.status() is AuthStatus.CONNECTED
    _assert_direct_callable_target()


def test_loaded_gh_dependency_reports_disconnected(mocker: MockerFixture) -> None:
    """AC4: The catalog dependency reports a posed closed session as disconnected."""
    dependency = _loaded_gh_dependency()
    mocker.patch.object(gh_auth_module, "gh_available", return_value=False)
    mocker.patch.object(
        gh_auth_module,
        "run_gh",
        return_value=_completed_gh_auth(returncode=1),
    )

    assert dependency.status() is AuthStatus.DISCONNECTED
    _assert_direct_callable_target()


def test_loaded_gh_dependency_reports_tool_absent(mocker: MockerFixture) -> None:
    """AC5: The catalog dependency reports a posed missing tool as absent."""
    dependency = _loaded_gh_dependency()
    mocker.patch.object(gh_auth_module, "gh_available", return_value=False)
    mocker.patch.object(gh_auth_module, "run_gh", side_effect=FileNotFoundError)

    assert dependency.status() is AuthStatus.TOOL_ABSENT
    _assert_direct_callable_target()
