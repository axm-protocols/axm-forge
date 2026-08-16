"""Integration coverage for opted-in per-case pytest reporting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core import test_runner
from axm_audit.tools.audit_test import AuditTestTool


def _write_suite(root: Path, source: str) -> str:
    test_file = root / "test_cases.py"
    test_file.write_text(source)
    return test_file.name


@pytest.mark.integration
def test_explicit_opt_out_keeps_real_run_payload_compact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC3: explicit false matches omission after a real filesystem pytest run."""
    test_file = _write_suite(
        tmp_path,
        """
def test_passes():
    assert 1 + 1 == 2


def test_fails():
    assert 1 + 1 == 3
""",
    )
    real_report = test_runner.run_tests(
        tmp_path,
        files=[test_file],
        stop_on_first=False,
    )
    seen_include_cases: list[object] = []

    def _reuse_report(*_args: object, **kwargs: object):
        seen_include_cases.append(kwargs.get("include_cases"))
        return real_report

    monkeypatch.setattr(test_runner, "run_tests", _reuse_report)

    default = AuditTestTool().execute(
        path=str(tmp_path),
        files=[test_file],
        stop_on_first=False,
    )
    explicit = AuditTestTool().execute(
        path=str(tmp_path),
        files=[test_file],
        stop_on_first=False,
        include_cases=False,
    )

    assert seen_include_cases == [False, False]
    assert default.data == explicit.data
    assert default.text == explicit.text
    assert explicit.data is not None
    assert explicit.data["passed"] == 1
    assert explicit.data["failed"] == 1
    assert "cases" not in explicit.data


@pytest.mark.integration
def test_opt_in_returns_every_real_collected_case_once(
    tmp_path: Path,
) -> None:
    """AC5: a complete real run keeps unique ids, details, skips, and xfails."""
    test_file = _write_suite(
        tmp_path,
        """
import pytest


@pytest.mark.parametrize(
    "value",
    [pytest.param(1, id="a-1"), pytest.param(2, id="b-2")],
)
def test_parametrized(value):
    assert value == 1


@pytest.mark.skip(reason="unsupported")
def test_skipped():
    assert True


@pytest.mark.xfail(reason="known mismatch")
def test_expected_failure():
    assert False
""",
    )

    result = AuditTestTool().execute(
        path=str(tmp_path),
        files=[test_file],
        stop_on_first=False,
        include_cases=True,
    )

    assert result.data is not None
    cases = result.data["cases"]
    assert isinstance(cases, list)
    node_ids = [case["node_id"] for case in cases]
    assert len(node_ids) == len(set(node_ids))
    assert set(node_ids) == {
        "test_cases.py::test_parametrized[a-1]",
        "test_cases.py::test_parametrized[b-2]",
        "test_cases.py::test_skipped",
        "test_cases.py::test_expected_failure",
    }
    failed = next(case for case in cases if case["outcome"] == "failed")
    assert isinstance(failed["detail"], str)
    assert failed["detail"]
    assert all(case["detail"] is None for case in cases if case["outcome"] == "passed")


def test_cases_mode_is_a_backward_compatible_evidence_alias(tmp_path: Path) -> None:
    """The historical mode field can request lossless evidence across caches."""
    test_file = _write_suite(
        tmp_path,
        """
def test_passes():
    assert 1 + 1 == 2
""",
    )

    result = AuditTestTool().execute(
        path=str(tmp_path),
        files=[test_file],
        stop_on_first=False,
        mode="cases",
    )

    assert result.data is not None
    assert [case["node_id"] for case in result.data["cases"]] == [
        "test_cases.py::test_passes"
    ]


@pytest.mark.integration
def test_corrupt_json_report_fails_closed_without_cases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC6: corrupt on-disk JSON is diagnosed through the opted-in tool path."""
    test_file = _write_suite(tmp_path, "def test_ok():\n    assert True\n")
    real_run_tests = test_runner.run_tests
    seen_include_cases: list[object] = []

    def _corrupt_report(
        cmd: list[str],
        _project_path: Path,
        **_kwargs: object,
    ) -> MagicMock:
        report_arg = next(arg for arg in cmd if arg.startswith("--json-report-file="))
        Path(report_arg.split("=", 1)[1]).write_text("{not-json")
        return MagicMock(returncode=1, stdout="", stderr="corrupt report")

    def _tracked_run(*args: object, **kwargs: object):
        seen_include_cases.append(kwargs.get("include_cases"))
        return real_run_tests(*args, **kwargs)

    monkeypatch.setattr(test_runner, "run_in_project", _corrupt_report)
    monkeypatch.setattr(test_runner, "run_tests", _tracked_run)

    result = AuditTestTool().execute(
        path=str(tmp_path),
        files=[test_file],
        include_cases=True,
    )

    assert seen_include_cases == [True]
    assert result.success is False
    assert result.error
    assert result.data is None or "cases" not in result.data


@pytest.mark.integration
def test_collection_error_fails_closed_without_measured_empty_cases(
    tmp_path: Path,
) -> None:
    """AC6: collection failure is an error, never a successful empty case list."""
    test_file = _write_suite(
        tmp_path,
        "raise RuntimeError('collection sentinel')\n",
    )

    result = AuditTestTool().execute(
        path=str(tmp_path),
        files=[test_file],
        stop_on_first=False,
        include_cases=True,
    )

    assert result.success is False
    assert result.error
    assert "collection" in result.error.lower()
    assert result.data is None or "cases" not in result.data


@pytest.mark.integration
def test_timeout_fails_closed_without_measured_empty_cases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC6: a subprocess timeout is diagnosed and never emits a case list."""
    test_file = _write_suite(tmp_path, "def test_ok():\n    assert True\n")

    monkeypatch.setattr(
        test_runner,
        "run_in_project",
        lambda *_args, **_kwargs: MagicMock(
            returncode=124,
            stdout="",
            stderr="Command timed out",
        ),
    )

    result = AuditTestTool().execute(
        path=str(tmp_path),
        files=[test_file],
        include_cases=True,
    )

    assert result.success is False
    assert result.error
    assert "timeout" in result.error.lower() or "timed out" in result.error.lower()
    assert result.data is None or "cases" not in result.data
