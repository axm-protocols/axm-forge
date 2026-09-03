"""Unit contracts for the GitHub CLI credential declaration."""

from __future__ import annotations

from importlib import import_module


def _gh_auth_credential() -> object:
    return import_module("axm_git.credentials").GH_AUTH_CREDENTIAL


def test_gh_auth_declaration_names_tool_and_commands() -> None:
    """AC1: The declaration identifies gh and its status/login commands."""
    declaration = _gh_auth_credential()

    assert declaration.name == "gh"
    assert declaration.status_command == "gh auth status"
    assert declaration.login_command == "gh auth login"


def test_gh_auth_declaration_genre_is_imported() -> None:
    """AC2: The declaration genre is owned outside axm_git."""
    declaration = _gh_auth_credential()

    assert not type(declaration).__module__.startswith("axm_git")
