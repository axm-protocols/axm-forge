from __future__ import annotations

import importlib
from types import ModuleType


def _gh_auth_module() -> ModuleType:
    return importlib.import_module("axm_git.core.gh_auth")


def test_classify_gh_auth_reports_not_installed() -> None:
    """AC1: An unavailable gh executable maps to not_installed."""
    gh_auth = _gh_auth_module()

    assert gh_auth.classify_gh_auth(available=False, returncode=None) == "not_installed"


def test_classify_gh_auth_reports_logged_out() -> None:
    """AC2: A non-zero auth status maps to logged_out."""
    gh_auth = _gh_auth_module()

    assert gh_auth.classify_gh_auth(available=True, returncode=1) == "logged_out"


def test_classify_gh_auth_reports_logged_in() -> None:
    """AC3: A zero auth status maps to logged_in."""
    gh_auth = _gh_auth_module()

    assert gh_auth.classify_gh_auth(available=True, returncode=0) == "logged_in"
