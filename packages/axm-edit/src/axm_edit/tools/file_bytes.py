"""Byte-exact inspection of a file already present on disk.

Strictly read-only: the file is opened once in binary mode (``rb``) and nothing
is ever written, created or renamed. Detection and verdict are delegated in
full to :func:`axm_edit.core.byte_report.build_report`; this module only
performs the I/O, maps the core report onto
:class:`axm_edit.models.file_bytes.FileBytesReport` and shapes the
``ToolResult``.

Lesson L4: what matters is the bytes actually present on disk after a write
routed through MCP, never a value Python has already decoded.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_edit.core.byte_report import ByteReport, LiteralEscape, build_report
from axm_edit.models.file_bytes import (
    FileBytesReport,
    LiteralEscapeOccurrence,
    MismatchReport,
    NonAsciiOccurrence,
)

__all__ = ["FileBytesTool", "render_text"]

_SUPPORTED_ENCODING = "utf-8"


def render_text(report: Mapping[str, object]) -> str:
    """Render a byte report as the compact text consumed by the CLI.

    Args:
        report: A serialised :class:`FileBytesReport`, or any equivalent flat
            report mapping.

    Returns:
        A header carrying the verdict and the sha256, followed by every
        integer counter the report holds (size and bounded totals), plus the
        remediation hint when the core produced one.
    """
    header = (
        f"file_bytes | verdict={report.get('verdict', 'unknown')}"
        f" | sha256={report.get('sha256', '')}"
    )
    counters = " ".join(
        f"{key}={report[key]}"
        for key in sorted(report)
        if isinstance(report[key], int) and not isinstance(report[key], bool)
    )
    line = f"{header} | {counters}" if counters else header
    hint = report.get("hint")
    return f"{line}\n  hint: {hint}" if isinstance(hint, str) and hint else line


def _escape_occurrence(text: str, escape: LiteralEscape) -> LiteralEscapeOccurrence:
    """Locate a core literal escape inside the decoded text.

    Args:
        text: The tolerantly decoded file content the core scanned.
        escape: The occurrence reported by the core, offset in characters.

    Returns:
        The serialisable occurrence, with its 1-indexed line, its column and
        its UTF-8 byte offset.
    """
    prefix = text[: escape.offset]
    return LiteralEscapeOccurrence(
        line=prefix.count("\n") + 1,
        col=escape.offset - (prefix.rfind("\n") + 1),
        sequence=escape.sequence,
        byte_offset=len(prefix.encode(_SUPPORTED_ENCODING)),
    )


def _as_model(report: ByteReport, text: str) -> FileBytesReport:
    """Map the core report onto its serialisable model, bounds included.

    Args:
        report: The report produced by the core.
        text: The tolerantly decoded content, used to place the escapes.

    Returns:
        The pydantic report, occurrence lists bounded exactly as the core
        bounded them and ``*_total`` counters preserved.
    """
    detail = report.mismatch
    mismatch = (
        None
        if detail is None
        else MismatchReport(
            first_diff_offset=detail.first_diff_offset,
            expected_repr=detail.expected_repr,
            actual_repr=detail.actual_repr,
        )
    )
    return FileBytesReport(
        sha256=report.sha256,
        size_bytes=report.size,
        encoding_ok=report.encoding_ok,
        verdict=report.verdict,
        non_ascii=[
            NonAsciiOccurrence(
                line=item.line,
                col=item.col,
                char=item.char,
                codepoint=item.codepoint,
                byte_offset=item.byte_offset,
            )
            for item in report.non_ascii
        ],
        literal_escapes=[
            _escape_occurrence(text, item) for item in report.literal_escapes
        ],
        non_ascii_total=report.non_ascii_total,
        literal_escapes_total=report.literal_escapes_total,
        mismatch=mismatch,
        hint=report.hint or None,
    )


class FileBytesTool(AXMTool):
    """Report what a file really contains, byte for byte, without writing.

    Orchestration and shaping layer only: every rule lives in
    :mod:`axm_edit.core.byte_report`. No code path opens the file for
    writing, so calling this tool can never change the target.
    """

    expose_directly = False
    domain = "edit"
    tags = frozenset({"edit", "bytes", "encoding", "verify"})

    agent_hint: str = (
        "Read-only byte-level report on a file: sha256, size, literal"
        " non-ASCII versus textual escape sequences, and divergence from an"
        " expected content. Call it after an MCP write to verify the bytes."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "file_bytes"

    def execute(
        self,
        *,
        path: str | None = None,
        expected: str | None = None,
        expect_escaped: bool = False,
        encoding: str = _SUPPORTED_ENCODING,
        **kwargs: object,
    ) -> ToolResult:
        """Inspect the bytes of one file, without ever touching the disk.

        Args:
            path: Absolute path to the file to inspect.
            expected: Content the caller believes it wrote, when known.
            expect_escaped: Whether escape sequences are expected verbatim
                on disk rather than the literal characters they denote.
            encoding: Decoding used to read the report; only ``utf-8``.
            kwargs: Ignored extra arguments (MCP forward-compatibility).

        Returns:
            ``ToolResult(success=True)`` with the serialised report in
            ``data`` — including the ``decode_error`` verdict, which is a
            diagnostic and not an execution failure; ``ToolResult(
            success=False, error=...)`` when the file could not be read.
            Never raises.
        """
        if not path:
            return ToolResult(success=False, error="Missing required argument: path")
        if encoding != _SUPPORTED_ENCODING:
            return ToolResult(
                success=False,
                error=f"Unsupported encoding: {encoding} (only {_SUPPORTED_ENCODING})",
            )

        target = Path(path).expanduser()
        try:
            data = target.read_bytes()
        except OSError as exc:
            return ToolResult(success=False, error=f"Read failed: {path}: {exc}")

        report = build_report(data, expected=expected, expect_escaped=expect_escaped)
        model = _as_model(report, data.decode(encoding, errors="replace"))
        payload: dict[str, object] = model.model_dump()
        payload["path"] = str(target)
        return ToolResult(success=True, data=payload, text=render_text(payload))
