"""Unit contracts for the GitHub CLI credential declaration."""

from __future__ import annotations

from importlib import import_module

from axm_vault import AuthDependencySpec, CredentialGroup


def _credential_groups() -> list[CredentialGroup]:
    provider = import_module("axm_git.credentials").GH_AUTH_CREDENTIAL
    assert callable(provider)
    groups = provider()
    assert isinstance(groups, list)
    assert all(isinstance(group, CredentialGroup) for group in groups)
    return groups


def test_credentials_provider_yields_one_gh_auth_dependency() -> None:
    """AC1: The declaration identifies gh and its status/login commands."""
    groups = _credential_groups()
    dependencies = [
        dependency for group in groups for dependency in group.auth_dependencies
    ]

    assert groups
    assert [dependency.name for dependency in dependencies].count("gh") == 1


def test_gh_auth_dependency_dump_matches_vault_model_fields() -> None:
    """AC2: The declaration genre is owned outside axm_git."""
    dependency = next(
        dependency
        for group in _credential_groups()
        for dependency in group.auth_dependencies
        if dependency.name == "gh"
    )
    dumped = dependency.model_dump()

    assert set(dumped) == set(AuthDependencySpec.model_fields)
    validated = AuthDependencySpec.model_validate(dependency)
    assert validated is dependency
