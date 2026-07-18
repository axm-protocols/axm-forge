"""Unit tests for the documentation-gate AXMTool (subprocess mocked)."""

from __future__ import annotations

import subprocess

from pytest_mock import MockerFixture

from axm_audit.doc_gate.tool import DocGateTool

_SAMPLE_OUTPUT = (
    "WARNING - Doc file 'index.md' contains a link 'missing.md' "
    "which is not found in the documentation files.\n"
    "WARNING - Doc file 'guide.md' contains a link to 'index.md#nope' "
    "with an unrecognized anchor.\n"
)


def _completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["mkdocs"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_execute_returns_structured_dual_format(mocker: MockerFixture) -> None:
    """AC1: execute returns a dual-format ToolResult from mkdocs output."""
    mocker.patch(
        "axm_audit.doc_gate.tool.subprocess.run",
        return_value=_completed(1, stderr=_SAMPLE_OUTPUT),
    )

    result = DocGateTool().execute(path=".")

    assert result.success is True
    kinds = [finding["kind"] for finding in result.data["findings"]]
    assert kinds == ["dead_link", "missing_anchor"]
    assert result.data["count"] == 2
    assert result.text is not None
    assert "doc_gate" in result.text


def test_execute_delegates_to_parse_mkdocs_output(mocker: MockerFixture) -> None:
    """AC2: execute delegates parsing to parse_mkdocs_output."""
    mocker.patch(
        "axm_audit.doc_gate.tool.subprocess.run",
        return_value=_completed(0, stdout="clean build output"),
    )
    spy = mocker.patch("axm_audit.doc_gate.tool.parse_mkdocs_output", return_value=[])

    DocGateTool().execute(path=".")

    spy.assert_called_once()
    (captured_output,) = spy.call_args.args
    assert "clean build output" in captured_output


def test_execute_missing_mkdocs_binary_fails_cleanly(
    mocker: MockerFixture,
) -> None:
    """AC3: a missing mkdocs binary yields a clean failure, not a crash."""
    mocker.patch(
        "axm_audit.doc_gate.tool.subprocess.run",
        side_effect=FileNotFoundError("mkdocs"),
    )

    result = DocGateTool().execute(path=".")

    assert result.success is False
    assert result.error is not None
    assert "mkdocs" in result.error.lower()


def test_execute_timeout_fails_cleanly(mocker: MockerFixture) -> None:
    """AC3: a subprocess timeout yields a clean failure mentioning timeout."""
    mocker.patch(
        "axm_audit.doc_gate.tool.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="mkdocs", timeout=1),
    )

    result = DocGateTool().execute(path=".")

    assert result.success is False
    assert result.error is not None
    assert "timed out" in result.error.lower()
