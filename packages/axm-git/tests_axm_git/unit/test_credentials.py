"""Unit contracts for the GitHub CLI credential declaration."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from axm_vault import AuthDependencySpec, CredentialGroup


def _credential_groups() -> list[CredentialGroup]:
    module = import_module("axm_git.credentials")
    assert module.GH_AUTH_CREDENTIAL is module.gh_credentials
    groups = module.gh_credentials()
    assert isinstance(groups, list)
    assert all(isinstance(group, CredentialGroup) for group in groups)
    return groups


def _exported_auth_dependency_type(module: ModuleType) -> type[AuthDependencySpec]:
    candidates = [
        candidate
        for name in module.__all__
        if isinstance((candidate := getattr(module, name)), type)
        and issubclass(candidate, AuthDependencySpec)
        and candidate is not AuthDependencySpec
    ]
    assert len(candidates) == 1
    return candidates[0]


def test_gh_credentials_returns_groups_containing_gh_dependency() -> None:
    """AC1: The declaration identifies gh and its status/login commands."""
    module = import_module("axm_git.credentials")
    groups = _credential_groups()
    dependencies = [
        dependency for group in groups for dependency in group.auth_dependencies
    ]

    assert groups
    assert all(isinstance(group, CredentialGroup) for group in groups)
    gh_dependencies = [
        dependency for dependency in dependencies if dependency.name == "gh"
    ]
    assert len(gh_dependencies) == 1
    assert isinstance(gh_dependencies[0], _exported_auth_dependency_type(module))


def test_gh_auth_dependency_subclass_declares_catalog_metadata() -> None:
    """AC2: The declaration genre is owned outside axm_git."""
    module = import_module("axm_git.credentials")
    dependency_type = _exported_auth_dependency_type(module)
    dependency = next(
        dependency
        for group in _credential_groups()
        for dependency in group.auth_dependencies
        if dependency.name == "gh"
    )

    assert isinstance(dependency, dependency_type)
    # Attest the exposed metadata, not which hierarchy level declares each
    # field: `login_command` is expected to move up into AuthDependencySpec.
    dumped = dependency.model_dump()
    assert {
        "package": dumped.get("package"),
        "status_command": dumped.get("status_command"),
        "login_command": dumped.get("login_command"),
    } == {
        "package": "axm-git",
        "status_command": "gh auth status",
        "login_command": "gh auth login",
    }
