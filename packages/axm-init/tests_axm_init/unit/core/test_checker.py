"""Unit tests for checker discovery and CLI lazy imports."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_init.checks._workspace import ProjectContext
from axm_init.core import checker
from axm_init.core.checker import (
    ALL_CHECKS,
    CheckEngine,
    format_agent,
    format_json,
    format_report,
    get_check_name,
    stamp_canonical_name,
)
from axm_init.models.check import CheckResult, ProjectResult


class TestCheckDiscovery:
    """Tests for auto-discovery of check modules."""

    def test_check_discovery_finds_all(self) -> None:
        """Auto-discovery finds 50 checks across 8 categories."""
        # AC6: the paper module adds two checks in a ninth category, and the
        # experiment module two more in a tenth one.
        total = sum(len(fns) for fns in ALL_CHECKS.values())
        assert total == 55
        assert len(ALL_CHECKS) == 10

    def test_discover_checks_includes_wheel_doc_shipping(self) -> None:
        """Auto-discovery picks up the wheel-doc-shipping check (AXM-1715)."""
        pyproject_fns = ALL_CHECKS.get("pyproject", [])
        names = {fn.__name__ for fn in pyproject_fns}
        assert "check_pyproject_wheel_doc_shipping" in names

    def test_discovery_categories(self) -> None:
        """All expected categories are discovered."""
        expected = {
            "pyproject",
            "ci",
            "tooling",
            "docs",
            "structure",
            "deps",
            "changelog",
            "workspace",
            "paper",
            "experiment",
        }
        assert set(ALL_CHECKS.keys()) == expected

    def test_discovery_skips_private_modules(self) -> None:
        """Private modules like _utils are not included."""
        assert "_utils" not in ALL_CHECKS

    def test_workspace_category_discovered(self) -> None:
        """workspace category exists in ALL_CHECKS with the expected 9 checks."""
        assert "workspace" in ALL_CHECKS
        assert len(ALL_CHECKS["workspace"]) == 10


class TestCLILazyImports:
    """Verify CLI adapter imports are lazy."""

    def test_cli_scaffold_lazy(self) -> None:
        """Importing axm_init.cli does not eagerly import adapters/core."""
        # Force reimport by checking that the modules are NOT loaded
        # as a side-effect of importing cli
        lazy_modules = [
            "axm_init.adapters.copier",
            "axm_init.adapters.credentials",
            "axm_init.adapters.pypi",
            "axm_init.core.reserver",
            "axm_init.core.templates",
        ]
        # Remove from cache if present
        cached = {m: sys.modules.pop(m, None) for m in lazy_modules}
        # Also remove cli to force re-evaluation
        original_cli = sys.modules.pop("axm_init.cli", None)
        try:
            import importlib

            importlib.import_module("axm_init.cli")
            for mod in lazy_modules:
                assert mod not in sys.modules, (
                    f"{mod} was eagerly imported by axm_init.cli"
                )
        finally:
            # Restore cache — including CLI itself to avoid breaking
            # @patch("axm_init.cli.X") in subsequent tests
            if original_cli is not None:
                sys.modules["axm_init.cli"] = original_cli
            for m, v in cached.items():
                if v is not None:
                    sys.modules[m] = v


# --- coverage_upload removal regression guards ---


def test_all_checks_no_coverage_upload():
    """After removal, _discover_checks() must not include coverage_upload."""
    from axm_init.checks import ci

    check_names = [
        fn.__name__
        for fn in vars(ci).values()
        if callable(fn) and getattr(fn, "__name__", "").startswith("check_")
    ]
    assert "check_ci_coverage_upload" not in check_names


def test_redirect_for_member_no_coverage_upload():
    """REDIRECT_FOR_MEMBER must not contain ci.ci_coverage_upload after removal."""
    member_redirects = _redirect_table()[ProjectContext.MEMBER]

    assert "ci.ci_coverage_upload" not in member_redirects


def test_all_checks_registry_populated() -> None:
    """ALL_CHECKS registry is populated with callable check functions."""
    from axm_init.core.checker import ALL_CHECKS

    assert isinstance(ALL_CHECKS, dict)
    assert len(ALL_CHECKS) > 0
    for category, fns in ALL_CHECKS.items():
        assert isinstance(category, str)
        assert all(callable(fn) for fn in fns)


def test_workspace_suite_uniqueness_check_is_discovered() -> None:
    """AC3: automatic discovery registers the uniqueness rule exactly once."""
    from axm_init.core.checker import ALL_CHECKS, get_check_name

    names = [get_check_name(fn) for fn in ALL_CHECKS["workspace"]]

    assert names.count("workspace.suite_dir_uniqueness") == 1
    assert len(names) == len(set(names))


# --- harmonized failures key in machine serializers ---
#
# AC1/AC2: ``format_json`` and ``format_agent`` must emit the failed-checks
# list under the SAME canonical top-level key ``"failures"`` (matching the
# source field ``ProjectResult.failures``) and never under ``"failed"``.


def _result_with_failure() -> ProjectResult:
    """Build an in-memory ProjectResult carrying exactly one failed check."""
    failing = CheckResult(
        name="has_license",
        category="structure",
        passed=False,
        weight=5,
        message="LICENSE file missing",
        details=["expected LICENSE at project root"],
        fix="add a LICENSE file",
    )
    return ProjectResult.from_checks(Path("/tmp/project"), [failing])


# --- AXM-2046: single canonical check-name convention --------------------
#
# SKIP / REDIRECT / exclude / display all key off the SAME string
# (``get_check_name``). These tests guard that unification: the displayed
# name agrees with the inferred name (AC1), excluding by that name actually
# skips the check (AC2), and every SKIP/REDIRECT entry still resolves to a
# real check after unification (AC4).


def _all_check_fns() -> list[Callable[[Path], CheckResult]]:
    """Flatten every discovered check function across all categories."""
    return [fn for fns in ALL_CHECKS.values() for fn in fns]


def test_check_name_single_convention() -> None:
    """AC1: stamped CheckResult.name agrees with get_check_name (one source).

    For every discovered check, re-stamping a result (even one carrying a
    divergent hand-set name) yields the canonical ``get_check_name`` value.
    """
    for fn in _all_check_fns():
        canonical = get_check_name(fn)
        assert canonical is not None, f"{fn!r} has no inferable check name"
        # A result with a deliberately wrong name must be re-stamped canonical.
        divergent = CheckResult(
            name="WRONG.name",
            category=canonical.split(".", 1)[0],
            passed=True,
            weight=1,
            message="",
            details=[],
            fix="",
        )
        stamped = stamp_canonical_name(fn, divergent)
        assert stamped.name == canonical


def test_exclude_actually_excludes() -> None:
    """AC2: excluding a canonical check name auto-passes that check.

    ``_apply_exclusions`` keys off the canonical name now stamped on results,
    so ``exclude = ["ci.ci_workflow_exists"]`` is no longer a silent no-op.
    """
    engine = CheckEngine.__new__(CheckEngine)  # no I/O: skip __init__ probing
    canonical = "ci.ci_workflow_exists"
    results = [
        CheckResult(
            name=canonical,
            category="ci",
            passed=False,
            weight=4,
            message="CI workflow not found",
            details=[],
            fix="",
        ),
        CheckResult(
            name="structure.src_layout",
            category="structure",
            passed=True,
            weight=4,
            message="ok",
            details=[],
            fix="",
        ),
    ]
    kept, excluded = engine._apply_exclusions(results, {canonical})
    excluded_result = next(r for r in kept if r.name == canonical)
    assert excluded_result.passed is True
    assert excluded_result.message == "Excluded by config"
    assert excluded == [canonical]
    # The unrelated check is untouched.
    src = next(r for r in kept if r.name == "structure.src_layout")
    assert src.message == "ok"


def test_skip_redirect_sets_unchanged_after_unification() -> None:
    """AC4: every SKIP/REDIRECT entry still resolves to a real check name.

    Guards against accidentally un-skipping / un-redirecting a check: each
    constant entry must equal ``get_check_name(fn)`` for some discovered fn.
    """
    canonical_names = {get_check_name(fn) for fn in _all_check_fns()}
    tabled = set().union(*_skip_table().values(), *_redirect_table().values())
    for entry in tabled:
        assert entry in canonical_names, (
            f"{entry!r} no longer resolves to a discovered check — "
            "a check was accidentally un-skipped/un-redirected"
        )


def test_json_and_agent_use_same_failures_key() -> None:
    """AC1/AC2: both serializers expose failures under ``"failures"``."""
    result = _result_with_failure()

    json_out = format_json(result)
    agent_out = format_agent(result)

    # Canonical key present in both.
    assert "failures" in json_out
    assert "failures" in agent_out

    # The divergent legacy key is absent from both.
    assert "failed" not in json_out
    assert "failed" not in agent_out

    # Both carry the single failed check under the canonical key.
    assert len(json_out["failures"]) == 1
    assert len(agent_out["failures"]) == 1
    assert json_out["failures"][0]["name"] == "has_license"
    assert agent_out["failures"][0]["name"] == "has_license"


def test_format_report_renders_na_for_not_applicable(tmp_path: Path) -> None:
    """AC3: a not-applicable result renders N/A, not '0/100 — Grade F'."""
    result = ProjectResult.from_checks(tmp_path, [])

    report = format_report(result)

    assert result.not_applicable
    assert "not applicable" in report.lower() or "N/A" in report
    assert "Score: 0/100" not in report
    assert "Grade F" not in report


def test_format_json_and_agent_null_score_grade_when_not_applicable(
    tmp_path: Path,
) -> None:
    """AC3: both serializers emit null score+grade for a not-applicable result."""
    result = ProjectResult.from_checks(tmp_path, [])

    json_out = format_json(result)
    agent_out = format_agent(result)

    assert json_out["score"] is None
    assert json_out["grade"] is None
    assert agent_out["score"] is None
    assert agent_out["grade"] is None


# --- context-keyed skip / redirect tables --------------------------------


def _context_table(name: str) -> dict[ProjectContext, frozenset[str]]:
    """Return the context-keyed table *name* the check engine must expose."""
    table: dict[ProjectContext, frozenset[str]] | None = getattr(checker, name, None)
    assert table is not None, f"axm_init.core.checker must expose {name}"
    return table


def _skip_table() -> dict[ProjectContext, frozenset[str]]:
    """The context-keyed skip table (AC1)."""
    return _context_table("SKIP_BY_CONTEXT")


def _redirect_table() -> dict[ProjectContext, frozenset[str]]:
    """The context-keyed redirect table (AC2)."""
    return _context_table("REDIRECT_BY_CONTEXT")


def _canonical_ids() -> set[str | None]:
    """Every canonical check id currently registered by discovery."""
    return {get_check_name(fn) for fn in _all_check_fns()}


def _validate_fn() -> Callable[[], object]:
    """The table validator the check engine must expose (AC3)."""
    validate: Callable[[], object] | None = getattr(
        checker, "validate_context_tables", None
    )
    assert validate is not None, (
        "axm_init.core.checker must expose validate_context_tables"
    )
    return validate


def test_skip_by_context_holds_the_golden_id_sets() -> None:
    """AC1: SKIP_BY_CONTEXT maps every context to a frozenset of real ids."""
    skip_table = _skip_table()

    assert set(skip_table) == set(ProjectContext)
    workspace_ids = skip_table[ProjectContext.WORKSPACE]
    member_ids = skip_table[ProjectContext.MEMBER]
    assert isinstance(workspace_ids, frozenset)
    assert isinstance(member_ids, frozenset)
    assert "docs.diataxis_nav" in workspace_ids
    assert "docs.diataxis_nav" in member_ids
    assert set(workspace_ids) <= _canonical_ids()
    assert set(member_ids) <= _canonical_ids()


def test_redirect_by_context_holds_the_member_ids() -> None:
    """AC2: REDIRECT_BY_CONTEXT redirects only for the member context."""
    redirect_table = _redirect_table()

    assert set(redirect_table) == set(ProjectContext)
    member_ids = redirect_table[ProjectContext.MEMBER]
    assert isinstance(member_ids, frozenset)
    assert member_ids
    assert set(member_ids) <= _canonical_ids()
    assert "ci.ci_coverage_upload" not in member_ids
    assert redirect_table[ProjectContext.STANDALONE] == frozenset()


def test_validate_context_tables_rejects_unregistered_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: an id no check declares raises ValueError naming that id."""
    validate = _validate_fn()
    bogus = "docs.no_such_check_id"
    table: dict[ProjectContext, frozenset[str]] = dict.fromkeys(
        ProjectContext, frozenset()
    )
    table[ProjectContext.MEMBER] = frozenset({bogus})
    monkeypatch.setattr(checker, "SKIP_BY_CONTEXT", table, raising=False)

    with pytest.raises(ValueError, match=bogus):
        validate()


def test_validate_context_tables_accepts_shipped_tables() -> None:
    """AC3: the shipped tables validate and the call returns None."""
    validate = _validate_fn()

    assert validate() is None


# --- paper checks are context-scoped -------------------------------------

PAPER_CHECK_IDS = frozenset({"paper.paper_structure", "paper.plan_present"})


def test_paper_checks_are_skipped_for_the_three_legacy_contexts() -> None:
    """AC6: both paper ids sit in the standalone/workspace/member skip sets."""
    skip_table = _skip_table()

    for context in (
        ProjectContext.STANDALONE,
        ProjectContext.WORKSPACE,
        ProjectContext.MEMBER,
    ):
        assert PAPER_CHECK_IDS <= set(skip_table[context])

    assert PAPER_CHECK_IDS & set(skip_table[ProjectContext.PAPER]) == set()
    assert PAPER_CHECK_IDS <= {get_check_name(fn) for fn in _all_check_fns()}


# --- experiment context placeholder --------------------------------------


def test_skip_by_context_keys_the_experiment_member_as_empty_placeholder() -> None:
    """AC5: the EXPERIMENT key exists, holds no id, and validation stays green."""
    skip_table = _skip_table()
    experiment = ProjectContext.EXPERIMENT

    assert experiment in skip_table
    assert set(skip_table[experiment]) == set()
    assert _validate_fn()() is None
