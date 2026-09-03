from __future__ import annotations

from pathlib import Path

from axm_git.core.runner import gh_available, run_gh

__all__ = ["classify_gh_auth", "gh_auth_state"]


def classify_gh_auth(available: bool, returncode: int | None) -> str:
    """Classify the GitHub CLI authentication state from observable process state."""
    if not available:
        return "not_installed"
    if returncode == 0:
        return "logged_in"
    return "logged_out"


def gh_auth_state() -> str:
    """Return the local GitHub CLI authentication state."""
    if gh_available():
        return classify_gh_auth(available=True, returncode=0)

    try:
        result = run_gh(["auth", "status"], Path.cwd())
    except FileNotFoundError:
        return classify_gh_auth(available=False, returncode=None)

    return classify_gh_auth(available=True, returncode=result.returncode)
