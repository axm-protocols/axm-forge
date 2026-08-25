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

    result = DocGateTool().execute(path=".")

    spy.assert_not_called()
    assert result.data["findings"] == []
    assert result.data["count"] == 0


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


def test_successful_strict_build_ignores_banner_output(
    mocker: MockerFixture,
) -> None:
    """AC1: a successful strict build makes captured banner output non-authoritative."""
    output = (
        "INFO    -  Building documentation...\n"
        "WARNING -  Material sponsor banner contains a link 'support.md' "
        "which is not found among the documentation files.\n"
        "INFO    -  Sponsor reference and anchor details are available online."
    )
    mocker.patch(
        "axm_audit.doc_gate.tool.subprocess.run",
        return_value=_completed(0, stdout=output),
    )

    result = DocGateTool().execute(path=".")

    assert result.success is True
    assert result.data["findings"] == []
    assert result.data["count"] == 0


def test_failed_strict_build_preserves_canonical_diagnostics(
    mocker: MockerFixture,
) -> None:
    """AC2: failed builds retain genuine diagnostics and reject lookalikes."""
    output = "\n".join(
        [
            (
                "WARNING -  Doc file 'index.md' contains a link 'missing.md' "
                "which is not found among the documentation files."
            ),
            (
                "WARNING -  Sponsor banner contains a link 'support.md' "
                "which is not found among the documentation files."
            ),
            (
                "WARNING -  Doc file 'guide.md' contains a link "
                "'other.md#missing' but the page does not contain an anchor "
                "'#missing'."
            ),
            "ERROR -  Theme link preview mentions an unrecognized anchor.",
            (
                "WARNING -  Doc file 'api.md' contains a bad reference "
                "'sym.func' that could not be resolved."
            ),
            "WARNING -  Sponsor reference could not be resolved.",
        ]
    )
    mocker.patch(
        "axm_audit.doc_gate.tool.subprocess.run",
        return_value=_completed(1, stderr=output),
    )

    result = DocGateTool().execute(path=".")

    assert [finding["kind"] for finding in result.data["findings"]] == [
        "dead_link",
        "missing_anchor",
        "bad_reference",
    ]
    assert result.data["count"] == 3
