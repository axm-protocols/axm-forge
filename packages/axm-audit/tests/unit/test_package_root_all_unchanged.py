"""AC9: promoted helpers must not leak into the package root __all__."""

from __future__ import annotations

_PRE_REFACTOR_ALL = frozenset(
    {
        "AuditResult",
        "CheckResult",
        "Severity",
        "__version__",
        "audit_project",
        "get_rules_for_category",
    }
)

_PROMOTED = frozenset(
    {
        "tarjan_scc",
        "classify_module_role",
        "build_coupling_result",
        "extract_imports",
        "read_coupling_config",
        "strip_prefix",
        "parse_overrides",
        "safe_int",
        "parse_collector_errors",
        "parse_coverage",
        "parse_failures",
        "parse_json_report",
        "build_pytest_cmd",
        "build_test_report",
        "find_venv",
        "read_diff_config",
    }
)


def test_package_root_all_unchanged() -> None:
    """Root __all__ identical to the pre-refactor snapshot."""
    import axm_audit

    assert set(axm_audit.__all__) == set(_PRE_REFACTOR_ALL)


def test_promoted_symbols_not_in_root_all() -> None:
    """Promoted helpers are *internal* public — they must not appear in root __all__."""
    import axm_audit

    leaked = _PROMOTED & set(axm_audit.__all__)
    assert not leaked, f"promoted symbols leaked into root __all__: {sorted(leaked)}"
