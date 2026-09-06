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
    extra_fields = set(dependency_type.model_fields) - set(
        AuthDependencySpec.model_fields
    )
    assert len(extra_fields) == 3
    dumped = dependency.model_dump()
    assert extra_fields <= set(dumped)
    assert sorted(dumped[name] for name in extra_fields) == [
        "axm-git",
        "gh auth login",
        "gh auth status",
    ]
