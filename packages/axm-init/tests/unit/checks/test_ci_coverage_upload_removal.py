from __future__ import annotations


def test_all_checks_no_coverage_upload():
    """After removal, _discover_checks() must not include coverage_upload."""
    # ci category
    from axm_init.checks import ci

    check_names = [
        fn.__name__
        for fn in vars(ci).values()
        if callable(fn) and getattr(fn, "__name__", "").startswith("check_")
    ]
    assert "check_ci_coverage_upload" not in check_names


def test_redirect_for_member_no_coverage_upload():
    """REDIRECT_FOR_MEMBER must not contain ci.ci_coverage_upload after removal."""
    from axm_init.core.checker import REDIRECT_FOR_MEMBER

    assert "ci.ci_coverage_upload" not in REDIRECT_FOR_MEMBER
