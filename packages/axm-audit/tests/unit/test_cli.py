"""Tests for CLI (cyclopts)."""

from __future__ import annotations

import contextlib
import io
import json

import pytest

from axm_audit.cli import app, audit, fix, version
from axm_audit.cli import test as cli_test
from axm_audit.cli import test_quality as cli_test_quality
from axm_audit.formatters import format_test_quality_json, format_test_quality_text
from axm_audit.models.results import AuditResult, CheckResult


class TestCLI:
    """Tests for CLI commands."""

    def test_version_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        """version command should print the package version to stdout."""
        from axm_audit import __version__
        from axm_audit.cli import version

        version()
        out = capsys.readouterr().out
        assert __version__ in out
        assert "axm-audit" in out

    def test_agent_flag_exists(self) -> None:
        """--agent flag should be accepted by audit command."""
        import inspect

        from axm_audit.cli import audit

        sig = inspect.signature(audit)
        assert "agent" in sig.parameters


# Test-failure extraction is exercised end-to-end through ``CoverageRule().check()``
# in ``tests/integration/test_coverage_rule_e2e.py``.


# ---------------------------------------------------------------------------
# --- merged from test_cli_category_help.py ---
# ---------------------------------------------------------------------------


def _capture_help() -> str:
    from axm_audit.cli import app

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        with pytest.raises(SystemExit):
            app(["audit", "--help"])
    return buf.getvalue()


def test_cli_category_help_lists_all_valid_categories() -> None:
    from axm_audit.core.auditor import VALID_CATEGORIES

    help_text = _capture_help()
    missing = [cat for cat in VALID_CATEGORIES if cat not in help_text]
    assert not missing, f"--category help missing: {missing}\n---\n{help_text}"


# ---------------------------------------------------------------------------
# --- merged from cli/test_main_test_quality_command.py ---
# ---------------------------------------------------------------------------


@pytest.fixture
def pyramid_mismatch_result() -> AuditResult:
    checks = [
        CheckResult(
            rule_id="test_quality",
            passed=False,
            message="pyramid mismatches found",
            details={},
            metadata={
                "pyramid_mismatches": [
                    {
                        "test": "tests/unit/test_a.py::test_a",
                        "current_dir": "unit",
                        "detected_level": "integration",
                    },
                    {
                        "test": "tests/unit/test_b.py::test_b",
                        "current_dir": "unit",
                        "detected_level": "unit",
                    },
                    {
                        "test": "tests/unit/test_c.py::test_c",
                        "current_dir": "unit",
                        "detected_level": "unit",
                    },
                ],
            },
        ),
    ]
    return AuditResult(project_path="/tmp/proj", checks=checks)


@pytest.fixture
def full_result() -> AuditResult:
    checks = [
        CheckResult(
            rule_id="private_imports",
            passed=False,
            message="private imports",
            details={},
            metadata={
                "private_import_violations": [
                    {"file": "tests/unit/test_x.py", "line": 3, "symbol": "_helper"},
                ],
            },
        ),
        CheckResult(
            rule_id="pyramid",
            passed=False,
            message="pyramid",
            details={},
            metadata={
                "pyramid_mismatches": [
                    {
                        "test": "tests/unit/test_y.py::test_y",
                        "current_dir": "unit",
                        "detected_level": "integration",
                    },
                ],
            },
        ),
        CheckResult(
            rule_id="duplicates",
            passed=False,
            message="duplicates",
            details={},
            metadata={
                "clusters": [
                    {
                        "signal": "signal1_call_assert",
                        "members": [
                            {
                                "test": "tests/unit/test_d.py::test_d",
                                "file": "tests/unit/test_d.py",
                                "line": 10,
                            },
                            {
                                "test": "tests/unit/test_e.py::test_e",
                                "file": "tests/unit/test_e.py",
                                "line": 20,
                            },
                        ],
                    },
                ],
                "buckets": {"signal1_call_assert": 1},
            },
        ),
        CheckResult(
            rule_id="tautologies",
            passed=False,
            message="tautologies",
            details={},
            metadata={
                "verdicts": [
                    {
                        "test": "step_n2_import_smoke",
                        "verdict": "DELETE",
                        "file": "tests/unit/t.py",
                        "line": 1,
                    },
                    {
                        "test": "step4c_significant_setup",
                        "verdict": "STRENGTHEN",
                        "file": "tests/unit/t.py",
                        "line": 2,
                    },
                    {
                        "test": "step5_default_unknown",
                        "verdict": "UNKNOWN",
                        "file": "tests/unit/t.py",
                        "line": 3,
                    },
                ],
            },
        ),
    ]
    return AuditResult(project_path="/tmp/proj", checks=checks)


def test_app_registers_expected_commands() -> None:
    """AC8: `fix` is registered alongside other top-level commands."""
    registered = list(app)
    names: list[str] = []
    for entry in registered:
        n = getattr(entry, "name", None)
        if isinstance(n, str):
            names.append(n)
        elif isinstance(n, (list, tuple)):
            names.extend(n)
    assert "test-quality" in names
    assert "fix" in names


def test_mismatches_only_filters_pyramid(pyramid_mismatch_result: AuditResult) -> None:
    out = format_test_quality_text(pyramid_mismatch_result, mismatches_only=True)
    pyramid_rows = [
        line
        for line in out.splitlines()
        if "test_a" in line or "test_b" in line or "test_c" in line
    ]
    assert len(pyramid_rows) == 1
    assert "test_a" in pyramid_rows[0]


def test_text_output_group_order(full_result: AuditResult) -> None:
    out = format_test_quality_text(full_result)
    lower = out.lower()
    idx_private = lower.find("private")
    idx_pyramid = lower.find("pyramid")
    idx_dup = lower.find("duplicate")
    idx_taut = lower.find("tautolog")
    assert 0 <= idx_private < idx_pyramid < idx_dup < idx_taut


@pytest.mark.parametrize(
    "expected",
    [
        pytest.param("[DELETE]", id="tautology-delete-tag"),
        pytest.param("[STRENGTHEN]", id="tautology-strengthen-tag"),
        pytest.param("[UNKNOWN]", id="tautology-unknown-tag"),
        pytest.param("signal1_call_assert", id="duplicate-signal-name"),
        pytest.param("tests/unit/test_d.py:10", id="duplicate-location"),
    ],
)
def test_text_output_contains_expected_tag(
    full_result: AuditResult, expected: str
) -> None:
    out = format_test_quality_text(full_result)
    assert expected in out


def test_json_output_superset(full_result: AuditResult) -> None:
    data = format_test_quality_json(full_result)
    assert isinstance(data, dict)
    for key in (
        "clusters",
        "verdicts",
        "pyramid_mismatches",
        "private_import_violations",
    ):
        assert key in data, f"missing key: {key}"
    json.dumps(data)


def test_version_prints_axm_audit_prefix(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`version` prints ``axm-audit <ver>`` to stdout."""
    version()
    out = capsys.readouterr().out
    assert out.startswith("axm-audit ")


def test_audit_invalid_path_exits_with_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`audit` on a non-directory path exits 1 and writes to stderr."""
    with pytest.raises(SystemExit) as excinfo:
        audit(path="/nonexistent/path/xyz-axm-cli")
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Not a directory" in err


def test_test_cli_invalid_path_exits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`test` exits 1 with stderr on a non-directory path."""
    with pytest.raises(SystemExit) as excinfo:
        cli_test(path="/nonexistent/xyz-test")
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Not a directory" in err


def test_test_quality_invalid_path_exits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`test-quality` exits 1 on a non-directory path."""
    with pytest.raises(SystemExit) as excinfo:
        cli_test_quality(path="/nonexistent/xyz-tq")
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Not a directory" in err


def test_fix_invalid_path_exits(capsys: pytest.CaptureFixture[str]) -> None:
    """`fix` exits 1 with stderr on a non-directory path."""
    with pytest.raises(SystemExit) as excinfo:
        fix(path="/nonexistent/xyz-fix")
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Not a directory" in err
