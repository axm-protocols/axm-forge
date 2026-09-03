from __future__ import annotations

from axm_vault import AuthDependencySpec, AuthStatus

from axm_git.core.gh_auth import gh_auth_state

__all__ = ["GH_AUTH_CREDENTIAL"]


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


GH_AUTH_CREDENTIAL = AuthDependencySpec(
    name="gh",
    source=_GhAuthSource(),
).model_copy(
    update={
        "status_command": "gh auth status",
        "login_command": "gh auth login",
        "check": gh_auth_state,
    }
)
