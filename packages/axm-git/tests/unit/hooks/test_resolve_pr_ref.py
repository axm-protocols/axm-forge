from __future__ import annotations

from axm_git.hooks.await_merge import _resolve_pr_ref


def test_resolve_pr_ref_from_params() -> None:
    """params with pr_number returns pr_number."""
    params = {"pr_number": 42}
    context: dict[str, object] = {}
    assert _resolve_pr_ref(params, context) == 42


def test_resolve_pr_ref_from_context() -> None:
    """params empty, context with pr_url returns pr_url."""
    params: dict[str, object] = {}
    context = {"pr_url": "https://github.com/org/repo/pull/99"}
    assert _resolve_pr_ref(params, context) == "https://github.com/org/repo/pull/99"


def test_resolve_pr_ref_missing() -> None:
    """Both empty returns None."""
    params: dict[str, object] = {}
    context: dict[str, object] = {}
    assert _resolve_pr_ref(params, context) is None


def test_resolve_pr_ref_params_takes_precedence() -> None:
    """When both params.pr_number and context.pr_url exist, params wins."""
    params = {"pr_number": 1}
    context = {"pr_url": "https://github.com/org/repo/pull/99"}
    assert _resolve_pr_ref(params, context) == 1
