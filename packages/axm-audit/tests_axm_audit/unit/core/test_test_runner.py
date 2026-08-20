"""Unit tests for axm_audit.core.test_runner (pure parsing, no I/O)."""

from __future__ import annotations

import dataclasses
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_audit.core.test_runner import (
    FailureDetail,
    parse_collector_errors,
    parse_failures,
    run_tests,
)

_PUBLIC = (
    "build_test_report",
    "parse_coverage",
    "parse_failures",
    "parse_json_report",
    "parse_collector_errors",
    "build_pytest_cmd",
)

_SETUP_ERROR_REPORT: dict[str, Any] = {
    "summary": {"passed": 0, "failed": 0, "error": 1},
    "tests": [
        {
            "nodeid": "tests/test_models.py::test_budget",
            "outcome": "error",
            "setup": {
                "crash": {
                    "path": "tests/test_models.py",
                    "lineno": 12,
                    "message": "ValidationError: 7 validation errors for BudgetData",
                },
                "longrepr": (
                    "line1\nline2\nline3\n"
                    "ValidationError: 7 validation errors for BudgetData"
                ),
            },
            # No "call" key — collection error
        },
    ],
}

_FAILING_REPORT: dict[str, Any] = {
    "summary": {
        "passed": 40,
        "failed": 2,
        "error": 0,
        "skipped": 0,
        "warnings": 0,
        "duration": 8.3,
    },
    "tests": [
        {"nodeid": "tests/test_foo.py::test_ok", "outcome": "passed"},
        {
            "nodeid": "tests/test_foo.py::TestClass::test_fail",
            "outcome": "failed",
            "call": {
                "crash": {
                    "path": "tests/test_foo.py",
                    "lineno": 54,
                    "message": "AssertionError: 0 != 1",
                },
                "longrepr": "line1\nline2\nline3\nline4\nline5\nline6\nline7",
            },
        },
        {
            "nodeid": "tests/test_bar.py::test_error",
            "outcome": "error",
            "call": {
                "crash": {
                    "path": "tests/test_bar.py",
                    "lineno": 10,
                    "message": "ImportError: no module named 'foo'",
                },
                "longrepr": "short tb",
            },
        },
    ],
}

_COLLECTOR_ERROR_ENTRIES: list[dict[str, Any]] = [
    {
        "nodeid": "tests/test_broken.py",
        "outcome": "failed",
        "longrepr": (
            "tests/test_broken.py:1: in <module>\n"
            "    import nonexistent\n"
            "ModuleNotFoundError: No module named 'nonexistent'"
        ),
    },
]


class TestParseFailures:
    def test_empty_list(self) -> None:
        assert parse_failures([]) == []

    def test_passing_tests_skipped(self) -> None:
        tests = [{"nodeid": "test_a", "outcome": "passed"}]
        assert parse_failures(tests) == []

    def test_failed_test_extracted(self) -> None:
        result = parse_failures(_FAILING_REPORT["tests"])
        assert len(result) == 2
        f = result[0]
        assert isinstance(f, FailureDetail)
        assert f.test == "tests/test_foo.py::TestClass::test_fail"
        assert f.error_type == "AssertionError"
        assert f.file == "tests/test_foo.py"
        assert f.line == 54

    def test_traceback_truncated(self) -> None:
        """Traceback longer than 5 lines is truncated."""
        result = parse_failures(_FAILING_REPORT["tests"])
        tb_lines = result[0].traceback.splitlines()
        assert len(tb_lines) <= 5

    def test_error_outcome_included(self) -> None:
        result = parse_failures(_FAILING_REPORT["tests"])
        err = result[1]
        assert err.error_type == "ImportError"
        assert err.test == "tests/test_bar.py::test_error"

    def test_parse_failures_collection_error(self) -> None:
        """Setup-phase errors (no 'call' key) produce non-empty FailureDetail."""
        result = parse_failures(_SETUP_ERROR_REPORT["tests"])
        assert len(result) == 1
        f = result[0]
        assert f.test == "tests/test_models.py::test_budget"
        assert f.error_type == "ValidationError"
        assert f.traceback != ""
        assert f.message != ""
        assert f.file == "tests/test_models.py"
        assert f.line == 12

    def test_parse_failures_call_error_unchanged(self) -> None:
        """Normal call-phase failures are unaffected by the fallback logic."""
        result = parse_failures(_FAILING_REPORT["tests"])
        assert len(result) == 2
        assert result[0].error_type == "AssertionError"
        assert result[0].file == "tests/test_foo.py"
        assert result[0].line == 54
        assert result[1].error_type == "ImportError"


class TestParseCollectorErrors:
    def test_empty_list(self) -> None:
        assert parse_collector_errors([]) == []

    def test_collector_without_longrepr_skipped(self) -> None:
        result = parse_collector_errors([{"nodeid": "foo", "longrepr": ""}])
        assert result == []

    def test_parse_failures_collector_error(self) -> None:
        """Collector-level errors produce FailureDetail with correct fields."""
        result = parse_collector_errors(_COLLECTOR_ERROR_ENTRIES)
        assert len(result) == 1
        f = result[0]
        assert f.test == "tests/test_broken.py"
        assert f.error_type == "ModuleNotFoundError"
        assert "nonexistent" in f.message
        assert f.traceback != ""


def test_test_runner_public_parsing_api() -> None:
    """All parsing helpers importable as public symbols."""
    from axm_audit.core import test_runner

    for name in _PUBLIC:
        assert hasattr(test_runner, name), f"missing public symbol: {name}"
        assert callable(getattr(test_runner, name))


@pytest.mark.parametrize("name", _PUBLIC)
def test_private_alias_removed(name: str) -> None:
    """Underscore-prefixed aliases removed (no shim left behind)."""
    from axm_audit.core import test_runner

    assert not hasattr(test_runner, f"_{name}"), (
        f"deprecated private alias _{name} still exposed"
    )


# --- build_test_report: unified report parsing ---


from axm_audit.core.test_runner import TestReport, build_test_report  # noqa: E402


def _make_report_data(*, num_failed: int = 0, num_passed: int = 5) -> dict[str, object]:
    """Build minimal pytest JSON report data."""
    tests: list[dict[str, object]] = []
    for i in range(num_passed):
        tests.append(
            {"nodeid": f"tests/test_ex.py::test_pass_{i}", "outcome": "passed"}
        )
    for i in range(num_failed):
        tests.append(
            {
                "nodeid": f"tests/test_ex.py::test_fail_{i}",
                "outcome": "failed",
                "call": {"longrepr": f"AssertionError: {i}"},
            }
        )
    return {
        "summary": {
            "passed": num_passed,
            "failed": num_failed,
            "error": 0,
            "skipped": 0,
            "warnings": 0,
        },
        "tests": tests,
        "duration": 1.0,
    }


class TestBuildReportAlwaysParsesFailures:
    """AC1: _build_test_report always parses failures — no mode branching."""

    def test_build_report_always_parses_failures(self):
        report_data = _make_report_data(num_failed=1)
        report = build_test_report(
            report_data=report_data,
            total_cov=80.0,
            per_file_cov={"src/a.py": 80.0},
        )
        assert report.failures is not None
        assert len(report.failures) == 1


class TestBuildReportCoverageNone:
    """AC4: coverage_by_file is None when no coverage data."""

    def test_build_report_coverage_none_when_empty(self):
        report_data = _make_report_data()
        report = build_test_report(
            report_data=report_data,
            total_cov=None,
            per_file_cov={},
        )
        assert report.coverage_by_file is None


class TestBuildReportFailuresNone:
    """AC5: failures is None when no failures exist."""

    def test_build_report_failures_none_when_no_fails(self):
        report_data = _make_report_data(num_failed=0)
        report = build_test_report(
            report_data=report_data,
            total_cov=90.0,
            per_file_cov={"src/a.py": 90.0},
        )
        assert report.failures is None


class TestCoverageRuleHandlesFailuresNone:
    """Edge: _report_to_result handles failures=None without crash."""

    def test_report_to_result_failures_none(self):
        from axm_audit.core.rules.coverage import TestCoverageRule

        rule = TestCoverageRule()
        report = TestReport(
            passed=5,
            failed=0,
            errors=0,
            coverage=80.0,
            failures=None,
        )
        result = rule._report_to_result(report)
        details = result.details
        assert details is not None
        assert details["failures"] == []


class TestDeprecatedDeltaMode:
    """Edge: delta mode accepted silently, same behavior as any other mode."""

    def test_delta_mode_same_behavior(self):
        report_data = _make_report_data(num_failed=1)
        per_file = {"src/a.py": 85.0}
        report = build_test_report(
            report_data=report_data,
            total_cov=85.0,
            per_file_cov=per_file,
        )
        assert report.coverage_by_file == per_file
        assert report.failures is not None
        assert len(report.failures) == 1


@pytest.mark.integration
class TestRunTestsIgnoresMode:
    """AC3: run_tests still accepts mode but ignores it."""

    def test_run_tests_ignores_mode(self, monkeypatch, tmp_path):
        report_data = _make_report_data(num_failed=1, num_passed=3)
        per_file = {"src/a.py": 75.0}

        monkeypatch.setattr(
            "axm_audit.core.test_runner.run_in_project",
            lambda *a, **kw: MagicMock(returncode=0),
        )
        monkeypatch.setattr(
            "axm_audit.core.test_runner.parse_json_report",
            lambda _: report_data,
        )
        monkeypatch.setattr(
            "axm_audit.core.test_runner.parse_coverage",
            lambda _: (75.0, per_file),
        )

        report = run_tests(tmp_path, mode="compact")

        # Coverage always collected even with compact mode
        assert report.coverage == 75.0
        assert report.coverage_by_file == per_file
        # Failures always parsed (was skipped for compact before)
        assert report.failures is not None
        assert len(report.failures) == 1


class TestSubprocessFailureDiagnostic:
    """AC2/AC3: the diagnostic is bounded, and a timeout keeps its own path."""

    def test_oversized_stderr_is_truncated_in_the_raised_message(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """AC2: a multi-kilobyte stderr is bounded, not dumped whole."""
        head = "HEAD-MARKER resolution failed\n"
        tail = "TAIL-MARKER last line of the dump\n"
        stderr = head + ("filler line of subprocess noise\n" * 400) + tail

        monkeypatch.setattr(
            "axm_audit.core.test_runner.run_in_project",
            lambda *a, **kw: MagicMock(returncode=1, stdout="", stderr=stderr),
        )

        with pytest.raises(ValueError) as excinfo:
            run_tests(tmp_path)

        message = str(excinfo.value)
        # The diagnostic must quote the head of the stderr...
        assert "HEAD-MARKER" in message, message[:200]
        # ...but stay bounded: the tail of a multi-kilobyte dump is dropped.
        assert "TAIL-MARKER" not in message, message[:200]
        assert len(message) < len(stderr), message[:200]

    def test_timed_out_run_short_circuits_before_the_new_error_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """AC3: returncode 124 keeps its own path while 1 takes the new one.

        Both branches are asserted in one test so the timeout short-circuit is
        witnessed *relative to* the new error path: a timeout must still yield
        ``TestReport(timed_out=True)`` where any other non-zero exit now raises.
        """
        monkeypatch.setattr(
            "axm_audit.core.test_runner.run_in_project",
            lambda *a, **kw: MagicMock(
                returncode=124, stdout="", stderr="Command timed out after 300s"
            ),
        )
        report = run_tests(tmp_path)
        assert report.timed_out is True

        # A non-timeout failure must NOT be reported as a timeout: it raises.
        monkeypatch.setattr(
            "axm_audit.core.test_runner.run_in_project",
            lambda *a, **kw: MagicMock(returncode=1, stdout="", stderr="SENTINEL boom"),
        )
        with pytest.raises(ValueError) as excinfo:
            run_tests(tmp_path)
        assert "SENTINEL boom" in str(excinfo.value), str(excinfo.value)


@pytest.mark.parametrize(
    ("target", "node_prefix"),
    [
        ("tests/test_ex.py", "tests/test_ex.py"),
        ("tests/test_ex.py::TestFeature", "tests/test_ex.py::TestFeature"),
    ],
)
def test_run_tests_retains_execution_and_target_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    target: str,
    node_prefix: str,
) -> None:
    """AC1: run_tests additively retains execution, collection, targets, verdict."""
    report_data = _make_report_data(num_passed=2)
    summary = report_data["summary"]
    assert isinstance(summary, dict)
    summary["collected"] = 2
    tests = report_data["tests"]
    assert isinstance(tests, list)
    for index, test in enumerate(tests):
        assert isinstance(test, dict)
        test["nodeid"] = f"{node_prefix}::test_pass_{index}"

    fake_tmp = MagicMock()
    fake_tmp.name = "/virtual/pytest-report.json"
    fake_tmp.close.return_value = None
    monkeypatch.setattr(
        "axm_audit.core.test_runner.tempfile.NamedTemporaryFile",
        lambda **_kwargs: fake_tmp,
    )
    monkeypatch.setattr(
        "axm_audit.core.test_runner.Path.unlink",
        lambda _self, **_kwargs: None,
    )
    monkeypatch.setattr(
        "axm_audit.core.test_runner.run_in_project",
        lambda *_args, **_kwargs: MagicMock(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        "axm_audit.core.test_runner.parse_json_report",
        lambda _path: report_data,
    )

    report = run_tests(tmp_path, files=[target])

    data = dataclasses.asdict(report)
    assert report.passed == 2
    assert report.failed == 0
    assert data["pytest_return_code"] == 0
    assert data["collected"] == 2
    assert data["target_statuses"] == [{"target": target, "status": "validated"}]
    assert data["verdict"] is True


_CASE_OUTCOMES = (
    "passed",
    "failed",
    "error",
    "skipped",
    "xfailed",
    "xpassed",
)


def _case_report(entries: object) -> dict[str, object]:
    return {
        "summary": {
            "passed": 1,
            "failed": 1,
            "error": 1,
            "skipped": 1,
            "warnings": 0,
        },
        "tests": entries,
        "duration": 0.25,
    }


def _build_case_report(
    entries: object,
    *,
    include_cases: bool = True,
) -> TestReport:
    return build_test_report(
        report_data=_case_report(entries),
        total_cov=None,
        per_file_cov={},
        include_cases=include_cases,
    )


def test_build_report_extracts_all_canonical_outcomes_and_exact_node_ids() -> None:
    """AC1: every canonical verdict keeps its exact parametrized pytest node id."""
    node_ids = [
        "tests_axm_audit/unit/test_sample.py::test_p[a-1]",
        "tests_axm_audit/unit/test_sample.py::test_failed",
        "tests_axm_audit/unit/test_sample.py::test_error",
        "tests_axm_audit/unit/test_sample.py::test_skipped",
        "tests_axm_audit/unit/test_sample.py::test_xfailed",
        "tests_axm_audit/unit/test_sample.py::test_xpassed",
    ]
    entries = [
        {"nodeid": node_id, "outcome": outcome}
        for node_id, outcome in zip(node_ids, _CASE_OUTCOMES, strict=True)
    ]

    report = _build_case_report(entries)
    by_node_id = {case.node_id: case.outcome for case in report.cases}

    assert by_node_id == dict(zip(node_ids, _CASE_OUTCOMES, strict=True))
    assert {case.outcome for case in report.cases} == set(_CASE_OUTCOMES)


def test_build_report_orders_cases_by_node_id_independently_of_input_order() -> None:
    """AC1: case ordering is deterministic for reversed source-report entries."""
    entries = [
        {
            "nodeid": f"tests_axm_audit/unit/test_sample.py::test_{suffix}",
            "outcome": outcome,
        }
        for suffix, outcome in zip(
            ("zeta", "alpha", "mu", "beta", "omega", "delta"),
            _CASE_OUTCOMES,
            strict=True,
        )
    ]

    forward = _build_case_report(entries)
    reversed_report = _build_case_report(list(reversed(entries)))
    expected = sorted(entry["nodeid"] for entry in entries)

    assert [case.node_id for case in forward.cases] == expected
    assert forward.cases == reversed_report.cases


def test_build_report_rejects_unknown_case_outcome() -> None:
    """AC2: an unknown outcome is diagnosed instead of coerced to passed."""
    entries = [
        {
            "nodeid": "tests_axm_audit/unit/test_sample.py::test_quarantined",
            "outcome": "quarantined",
        }
    ]

    with pytest.raises(ValueError, match="quarantined"):
        _build_case_report(entries)


def test_build_report_rejects_duplicate_case_node_id() -> None:
    """AC2: duplicate node ids are diagnosed instead of silently deduplicated."""
    node_id = "tests_axm_audit/unit/test_sample.py::test_duplicate"
    entries = [
        {"nodeid": node_id, "outcome": "passed"},
        {"nodeid": node_id, "outcome": "failed"},
    ]

    with pytest.raises(ValueError, match="test_duplicate"):
        _build_case_report(entries)


def test_build_report_captures_non_passed_detail_only() -> None:
    """AC5: failure diagnostics are retained while passed cases stay detail-free."""
    entries = [
        {
            "nodeid": "tests_axm_audit/unit/test_sample.py::test_failed",
            "outcome": "failed",
            "call": {
                "crash": {"message": "AssertionError: expected parity"},
                "longrepr": "traceback line\nAssertionError: expected parity",
            },
        },
        {
            "nodeid": "tests_axm_audit/unit/test_sample.py::test_passed",
            "outcome": "passed",
            "call": {"longrepr": "must not leak into passed detail"},
        },
    ]

    report = _build_case_report(entries)
    cases = {case.outcome: case for case in report.cases}

    assert cases["failed"].detail
    assert "expected parity" in cases["failed"].detail
    assert cases["passed"].detail is None


def test_build_report_explicit_opt_out_keeps_counts_and_empty_cases() -> None:
    """AC3: include_cases=False is accepted and changes no aggregate count."""
    entries = [
        {
            "nodeid": f"tests_axm_audit/unit/test_sample.py::test_{outcome}",
            "outcome": outcome,
        }
        for outcome in _CASE_OUTCOMES
    ]

    included = _build_case_report(entries)
    excluded = _build_case_report(entries, include_cases=False)

    assert excluded.cases == ()
    assert (
        excluded.passed,
        excluded.failed,
        excluded.errors,
        excluded.skipped,
    ) == (
        included.passed,
        included.failed,
        included.errors,
        included.skipped,
    )


@pytest.mark.parametrize(
    "report_data",
    [
        pytest.param({"summary": {}}, id="missing-tests"),
        pytest.param({"summary": {}, "tests": {"not": "a list"}}, id="tests-not-list"),
    ],
)
def test_build_report_rejects_structurally_corrupt_case_data(
    report_data: dict[str, object],
) -> None:
    """AC6: malformed case data is diagnosed rather than measured as empty."""
    with pytest.raises(ValueError, match="tests"):
        build_test_report(
            report_data=report_data,
            total_cov=None,
            per_file_cov={},
            include_cases=True,
        )


def test_test_report_defaults_the_non_test_cause_to_none_and_serializes_it() -> None:
    """AC1: a green report exposes non_test_cause=None and keeps the key.

    The field is a pure additive schema entry: an in-memory report built
    without any classification must expose it as ``None`` and still emit the
    key in its serialized payload, so no existing JSON consumer breaks.
    """
    report = TestReport(passed=3, failed=0, errors=0, duration=0.1, coverage=90.0)

    payload = (
        report.model_dump()
        if hasattr(report, "model_dump")
        else dataclasses.asdict(report)
    )

    assert report.non_test_cause is None
    assert "non_test_cause" in payload
    assert payload["non_test_cause"] is None
