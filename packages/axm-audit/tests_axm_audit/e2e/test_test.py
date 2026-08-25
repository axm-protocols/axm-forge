"""E2E test for axm-audit `test` CLI: --mode flag absent from --help."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest


class TestCliNoModeFlag:
    def test_cli_no_mode_flag(self):
        """CLI 'test --help' must not expose a --mode flag."""
        proc = subprocess.run(
            [sys.executable, "-m", "axm_audit", "test", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--mode" not in proc.stdout, "--mode flag should be removed from CLI"


_TOOL_SCRIPT = """
import json
import sys
from axm_audit.tools.audit_test import AuditTestTool

result = AuditTestTool().execute(path=sys.argv[1], files=sys.argv[2:])
print(json.dumps({
    "success": result.success,
    "data": result.data,
    "text": result.text,
    "error": result.error,
}))
"""


def _invoke_audit_test(project: Path, *targets: str) -> dict[str, object]:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _TOOL_SCRIPT, str(project), *targets],
        capture_output=True,
        text=True,
        check=True,
    )
    return cast("dict[str, object]", json.loads(proc.stdout))


def _assert_external_consistency(
    response: dict[str, object], *, expected_success: bool
) -> dict[str, object]:
    data = response["data"]
    assert isinstance(data, dict)
    text = response["text"]
    assert isinstance(text, str)
    assert response["success"] is expected_success
    assert data["verdict"] is expected_success
    assert ("✅" in text) is expected_success
    return data


@pytest.mark.e2e
def test_one_requested_file_with_multiple_tests_succeeds(tmp_path: Path) -> None:
    """AC2/AC6: one multi-test target is valid and all verdicts stay green."""
    (tmp_path / "test_many.py").write_text(
        "def test_one():\n    assert 1 == 1\n\ndef test_two():\n    assert 2 == 2\n",
        encoding="utf-8",
    )

    response = _invoke_audit_test(tmp_path, "test_many.py")
    data = _assert_external_consistency(response, expected_success=True)

    assert data["collected"] == 2
    assert data["target_statuses"] == [
        {"target": "test_many.py", "status": "validated"}
    ]


def test_requested_file_ignores_project_wide_coverage_threshold(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'addopts = ["--cov=sample", "--cov-fail-under=100"]\n',
        encoding="utf-8",
    )
    (tmp_path / "sample.py").write_text(
        "def branch(value: bool) -> int:\n"
        "    if value:\n"
        "        return 1\n"
        "    return 0\n",
        encoding="utf-8",
    )
    (tmp_path / "test_sample.py").write_text(
        "from sample import branch\n\n"
        "def test_branch():\n"
        "    assert branch(True) == 1\n",
        encoding="utf-8",
    )

    response = _invoke_audit_test(tmp_path, "test_sample.py")
    data = _assert_external_consistency(response, expected_success=True)

    assert data["pytest_return_code"] == 0
    assert data["passed"] == 1


@pytest.mark.e2e
def test_real_zero_collection_fails_closed(tmp_path: Path) -> None:
    """AC3/AC6: a real zero-test target reports zero and fails everywhere."""
    (tmp_path / "test_empty.py").write_text(
        "def helper():\n    return 1\n",
        encoding="utf-8",
    )

    response = _invoke_audit_test(tmp_path, "test_empty.py")
    data = _assert_external_consistency(response, expected_success=False)

    assert data["collected"] == 0
    assert "0 collected" in str(response["text"])


@pytest.mark.e2e
def test_real_missing_target_is_identified(tmp_path: Path) -> None:
    """AC4/AC6: a real mistyped target is named and fails every outcome."""
    response = _invoke_audit_test(tmp_path, "test_mispelled.py")
    data = _assert_external_consistency(response, expected_success=False)

    assert data["target_statuses"] == [
        {"target": "test_mispelled.py", "status": "missing"}
    ]
    assert "test_mispelled.py" in str(response["text"])


@pytest.mark.e2e
def test_real_omitted_target_cannot_hide_behind_collection(tmp_path: Path) -> None:
    """AC4/AC6: an omitted target fails despite another collected test."""
    (tmp_path / "test_ok.py").write_text(
        "def test_ok():\n    assert 1 == 1\n",
        encoding="utf-8",
    )
    (tmp_path / "test_empty.py").write_text(
        "def helper():\n    return 1\n",
        encoding="utf-8",
    )

    response = _invoke_audit_test(tmp_path, "test_ok.py", "test_empty.py")
    data = _assert_external_consistency(response, expected_success=False)

    assert data["collected"] == 1
    assert data["target_statuses"] == [
        {"target": "test_ok.py", "status": "validated"},
        {"target": "test_empty.py", "status": "omitted"},
    ]
    assert "test_empty.py" in str(response["text"])


@pytest.mark.e2e
def test_real_non_success_exit_overrides_empty_failures(tmp_path: Path) -> None:
    """AC5/AC6: a forced pytest exit 3 fails with no failed test records."""
    (tmp_path / "conftest.py").write_text(
        "def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 3\n",
        encoding="utf-8",
    )
    (tmp_path / "test_ok.py").write_text(
        "def test_ok():\n    assert 1 == 1\n",
        encoding="utf-8",
    )

    response = _invoke_audit_test(tmp_path, "test_ok.py")
    data = _assert_external_consistency(response, expected_success=False)

    assert data["pytest_return_code"] == 3
    assert data["failed"] == 0
    assert data["errors"] == 0
    assert "pytest exit 3" in str(response["text"])


def _write_cov_threshold_project(root: Path) -> None:
    """Write a project whose green suite still misses its coverage gate."""
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'addopts = ["--cov=covpkg", "--cov-fail-under=100"]\n',
        encoding="utf-8",
    )
    (root / "covpkg.py").write_text(
        "def classify(value: int) -> str:\n"
        "    if value < 0:\n"
        '        return "negative"\n'
        '    return "positive"\n',
        encoding="utf-8",
    )
    (root / "test_covpkg.py").write_text(
        "from covpkg import classify\n\n"
        "def test_classify_positive():\n"
        '    assert classify(1) == "positive"\n',
        encoding="utf-8",
    )


@pytest.mark.e2e
def test_cli_test_prints_the_non_test_cause(tmp_path: Path) -> None:
    """AC4: the shipped test command exits red and names the cause on stdout."""
    _write_cov_threshold_project(tmp_path)

    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "axm_audit", "test", str(tmp_path), "--agent"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "coverage_threshold" in proc.stdout
