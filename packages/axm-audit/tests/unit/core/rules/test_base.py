"""Tests for base module — ProjectRule ABC and scoring constants."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from axm_audit.models.results import CheckResult


class TestProjectRuleAbstract:
    """Tests for ProjectRule ABC surface (no I/O)."""

    def test_is_abstract(self) -> None:
        """ProjectRule cannot be instantiated directly."""
        from axm_audit.core.rules.base import ProjectRule

        with pytest.raises(TypeError):
            ProjectRule()  # type: ignore[abstract]

    @pytest.mark.parametrize("attr_name", ["rule_id", "check"])
    def test_declares_abstract_attribute(self, attr_name: str) -> None:
        """ProjectRule declares the abstract surface (rule_id, check)."""
        from axm_audit.core.rules.base import ProjectRule

        assert hasattr(ProjectRule, attr_name)
        assert attr_name in ProjectRule.__abstractmethods__

    def test_has_category_property(self) -> None:
        """category is concrete, auto-injected by @register_rule."""
        from axm_audit.core.rules.base import ProjectRule

        assert hasattr(ProjectRule, "category")
        # category is no longer abstract — it reads from _registered_category
        assert "category" not in ProjectRule.__abstractmethods__


class TestScoringConstants:
    """Tests for shared scoring constants."""

    def test_pass_threshold_value(self) -> None:
        """PASS_THRESHOLD should be 90."""
        from axm_audit.core.rules.base import PASS_THRESHOLD

        assert PASS_THRESHOLD == 90

    def test_perfect_score_value(self) -> None:
        """PERFECT_SCORE should be 100."""
        from axm_audit.core.rules.base import PERFECT_SCORE

        assert PERFECT_SCORE == 100


class TestRegisterRule:
    """Tests for @register_rule decorator."""

    def test_register_rule_populates_registry(self) -> None:
        """Decorated class appears in the registry."""
        from axm_audit.core.rules.base import _RULE_REGISTRY, ProjectRule, register_rule

        @register_rule("_test_cat")
        class _DummyRule(ProjectRule):
            @property
            def rule_id(self) -> str:
                return "DUMMY"

            def check(self, project_path: Path) -> CheckResult:
                return CheckResult(rule_id=self.rule_id, passed=True, message="ok")

        assert _DummyRule in _RULE_REGISTRY["_test_cat"]
        # Cleanup
        _RULE_REGISTRY["_test_cat"].remove(_DummyRule)
        if not _RULE_REGISTRY["_test_cat"]:
            del _RULE_REGISTRY["_test_cat"]

    def test_registry_deduplication(self) -> None:
        """Registering the same class twice doesn't duplicate it."""
        from axm_audit.core.rules.base import _RULE_REGISTRY, ProjectRule, register_rule

        @register_rule("_test_dedup")
        class _DedupeRule(ProjectRule):
            @property
            def rule_id(self) -> str:
                return "DEDUPE"

            def check(self, project_path: Path) -> CheckResult:
                return CheckResult(rule_id=self.rule_id, passed=True, message="ok")

        # Register again manually
        register_rule("_test_dedup")(_DedupeRule)

        assert _RULE_REGISTRY["_test_dedup"].count(_DedupeRule) == 1
        # Cleanup
        _RULE_REGISTRY["_test_dedup"].remove(_DedupeRule)
        if not _RULE_REGISTRY["_test_dedup"]:
            del _RULE_REGISTRY["_test_dedup"]


class TestGetRegistry:
    """Tests for get_registry()."""

    def test_registry_has_all_categories(self) -> None:
        """Registry contains all expected auditor categories after import."""
        import axm_audit.core.rules  # noqa: F401
        from axm_audit.core.rules.base import get_registry

        reg = get_registry()
        expected = {
            "lint",
            "type",
            "complexity",
            "architecture",
            "practices",
            "security",
            "deps",
            "testing",
            "structure",
            "tooling",
            "test_quality",
        }
        assert expected == set(reg.keys())

    def test_registry_total_rule_count(self) -> None:
        """Registry contains 28 total rule classes (adds NoPackageSymbolRule)."""
        import axm_audit.core.rules  # noqa: F401
        from axm_audit.core.rules.base import get_registry

        reg = get_registry()
        total = sum(len(v) for v in reg.values())
        assert total == 28


# --- Canonical imports (API publique) ---


class TestCanonicalImports:
    """Canonical paths expose register_rule, ProjectRule, get_registry, models."""

    def test_canonical_imports_resolve(self) -> None:
        from axm_audit.core.rules.base import (
            ProjectRule,
            get_registry,
            register_rule,
        )
        from axm_audit.models.results import AuditResult, CheckResult, Severity

        decorator = register_rule("lint")
        assert callable(decorator)
        assert Severity.ERROR.value == "error"
        assert issubclass(CheckResult, BaseModel)
        assert issubclass(AuditResult, BaseModel)
        assert isinstance(get_registry(), dict)
        assert ProjectRule.__name__ == "ProjectRule"


# --- Package root __all__ (gel API publique) ---


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


class TestPackageRootAll:
    """Garde-fou : promoted helpers ne doivent pas fuiter dans axm_audit.__all__."""

    def test_package_root_all_unchanged(self) -> None:
        """Root __all__ identical to the pre-refactor snapshot."""
        import axm_audit

        assert set(axm_audit.__all__) == set(_PRE_REFACTOR_ALL)

    def test_promoted_symbols_not_in_root_all(self) -> None:
        """Promoted helpers are *internal* public — must not appear in root __all__."""
        import axm_audit

        leaked = _PROMOTED & set(axm_audit.__all__)
        assert not leaked, (
            f"promoted symbols leaked into root __all__: {sorted(leaked)}"
        )
