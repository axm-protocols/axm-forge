from __future__ import annotations

from axm_vault import AuthDependencySpec, AuthStatus, CredentialGroup

from axm_git.core.gh_auth import gh_auth_state

__all__ = ["GH_AUTH_CREDENTIAL", "GhAuthDependency", "gh_credentials"]


class _GhAuthSource:
    """Expose the GitHub CLI session through the vault auth-source contract."""

    def status(self) -> AuthStatus:
        match gh_auth_state():
            case "logged_in":
                return AuthStatus.CONNECTED
            case "not_installed":
                return AuthStatus.TOOL_ABSENT
            case _:
                return AuthStatus.DISCONNECTED


class GhAuthDependency(AuthDependencySpec):  # type: ignore[explicit-any]
    """GitHub CLI authentication dependency with catalog metadata."""

    package: str
    status_command: str
    login_command: str

    def __init__(
        self,
        *,
        name: str,
        source: object,
        package: str,
        status_command: str,
        login_command: str,
    ) -> None:
        super().__init__(
            name=name,
            source=source,
            package=package,
            status_command=status_command,
            login_command=login_command,
        )


def gh_credentials() -> list[CredentialGroup]:
    """Declare the GitHub CLI session consumed by axm-git."""
    dependency = GhAuthDependency(
        name="gh",
        source=_GhAuthSource(),
        package="axm-git",
        status_command="gh auth status",
        login_command="gh auth login",
    )
    group = CredentialGroup(
        id="gh",
        package="axm-git",
        title="GitHub CLI",
        specs=(),
        auth_dependencies=(dependency,),
    )
    return [group]


GH_AUTH_CREDENTIAL = gh_credentials
