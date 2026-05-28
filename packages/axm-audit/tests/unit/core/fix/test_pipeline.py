"""Unit tests for axm_audit.core.fix.pipeline helper/dispatch functions."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.fix.models import PipelineReport
from axm_audit.core.fix.pipeline import (
    DEFAULT_RULES,
    _filter_helper_dup_warnings,
    _is_duplicated_helper_warning,
    _parse_extracted_names,
    _ruff_format_tests,
    _run_dryrun_ops,
    run,
)

# ---------------------------------------------------------------------------
# Pure helpers — parsing & filtering messages
# ---------------------------------------------------------------------------


def test_parse_extracted_names_extracts_helper_and_fixture_names() -> None:
    """Both ``extracted helper`` and ``extracted fixture`` lines are parsed."""
    msgs = [
        "extracted helper `gold_project` from 3 files",
        "extracted fixture `make_db` from 2 files",
        "unrelated message without a backtick",
        "some other status",
    ]
    assert _parse_extracted_names(msgs) == {"gold_project", "make_db"}


def test_parse_extracted_names_skips_messages_missing_backtick() -> None:
    msgs = ["extracted helper no_backticks", "extracted fixture also missing"]
    assert _parse_extracted_names(msgs) == set()


def test_is_duplicated_helper_warning_matches_known_name() -> None:
    """Warning text matches when it mentions a duplicated, extracted helper."""
    warning = "Helper 'gold_project' duplicated in target tests/integration/test_x.py"
    assert _is_duplicated_helper_warning(warning, {"gold_project"}) is True


def test_is_duplicated_helper_warning_rejects_when_not_duplicated() -> None:
    warning = "Helper 'gold_project' was overwritten"
    assert _is_duplicated_helper_warning(warning, {"gold_project"}) is False


def test_is_duplicated_helper_warning_rejects_unknown_name() -> None:
    warning = "Helper 'something_else' duplicated in target file.py"
    assert _is_duplicated_helper_warning(warning, {"gold_project"}) is False


def test_filter_helper_dup_warnings_keeps_unrelated() -> None:
    """Filtering removes only duplicate-warnings tied to extracted names."""
    extracted = {"gold_project"}
    warnings = [
        "Helper 'gold_project' duplicated in target test_a.py",
        "some unrelated warning",
        "Helper 'other' duplicated in target test_b.py",
    ]
    out = _filter_helper_dup_warnings(warnings, extracted)
    assert "some unrelated warning" in out
    assert "Helper 'other' duplicated in target test_b.py" in out
    assert all("gold_project" not in w for w in out)


def test_filter_helper_dup_warnings_noop_when_no_extracted_names() -> None:
    """Empty extracted set returns the input list verbatim."""
    warnings = ["a", "b"]
    assert _filter_helper_dup_warnings(warnings, set()) == warnings


# ---------------------------------------------------------------------------
# Dryrun ops
# ---------------------------------------------------------------------------


def test_run_dryrun_ops_extends_report_and_returns_count() -> None:
    """_run_dryrun_ops appends ops onto report and returns len(ops)."""
    report = PipelineReport(applied=False)
    sentinel = [object(), object(), object()]
    count = _run_dryrun_ops(sentinel, report)
    assert count == 3
    assert report.ops == sentinel


# ---------------------------------------------------------------------------
# Public ``run`` smoke (empty project)
# ---------------------------------------------------------------------------


def test_run_dryrun_on_empty_project_yields_no_ops(tmp_path: Path) -> None:
    """Dry-run on a project without ``tests/`` returns an empty report."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\nversion="0"\n')
    (tmp_path / "src" / "x").mkdir(parents=True)
    (tmp_path / "src" / "x" / "__init__.py").write_text("")
    report = run(tmp_path, apply=False)
    assert report.applied is False
    assert report.iterations == 1
    assert report.ops == []


def test_run_respects_custom_rule_set(tmp_path: Path) -> None:
    """Passing an empty rules set runs neither pyramid nor naming stages."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\nversion="0"\n')
    (tmp_path / "src" / "x").mkdir(parents=True)
    (tmp_path / "src" / "x" / "__init__.py").write_text("")
    report = run(tmp_path, apply=False, rules=set())
    assert report.ops == []


def test_default_rules_contains_pyramid_and_naming() -> None:
    """DEFAULT_RULES is the documented PYRAMID + FILE_NAMING pair."""
    assert DEFAULT_RULES == frozenset(
        {"TEST_QUALITY_PYRAMID_LEVEL", "TEST_QUALITY_FILE_NAMING"}
    )


# ---------------------------------------------------------------------------
# _ruff_format_tests
# ---------------------------------------------------------------------------


def test_ruff_format_tests_returns_empty_without_tests_dir(tmp_path: Path) -> None:
    """No-op when ``tests/`` is missing."""
    assert _ruff_format_tests(tmp_path) == []
