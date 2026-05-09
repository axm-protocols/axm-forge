"""Text renderers for GitCommitTool dual-format ToolResult.

These helpers transform the structured ``data`` dict produced by
:class:`axm_git.tools.commit.GitCommitTool` into a compact, token-efficient
text representation suitable for MCP consumers.

The header pattern follows the AXM convention
(see ``axm_ast.tools.search_text``)::

    git_commit | {status} | {succeeded}/{total} commits [· {extra}]
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "format_commit_line",
    "format_text_header",
    "render_failure_text",
    "render_text",
]


def format_text_header(
    *,
    status: str,
    succeeded: int,
    total: int,
    retried_count: int = 0,
    extra: str | None = None,
) -> str:
    """Build the header line for a ``git_commit`` text rendering.

    When *total* is 0 and *extra* is given, emit the pure-error shape
    ``git_commit | error: {extra}`` (used for early failures with no
    commit list available).
    """
    if total == 0 and extra is not None:
        return f"git_commit | error: {extra}"
    sections = ["git_commit", status, f"{succeeded}/{total} commits"]
    header = " | ".join(sections)
    if retried_count > 0:
        header += f" · {retried_count} retried"
    if extra:
        header += f" · {extra}"
    return header


def format_commit_line(result: dict[str, Any]) -> str:
    """Format one successful commit record as ``{sha} [↻ ]{message}``."""
    sha = result.get("sha", "")
    message = result.get("message", "")
    if result.get("retried"):
        return f"{sha} ↻ {message}"
    return f"{sha} {message}"


def _retried_count(results: list[dict[str, Any]]) -> int:
    """Count entries in *results* that were retried after a hook auto-fix."""
    return sum(1 for r in results if r.get("retried"))


def render_text(data: dict[str, Any]) -> str:
    """Render the success-path ``data`` dict.

    Header + one ``format_commit_line`` per entry in ``data['results']``.
    """
    results: list[dict[str, Any]] = data.get("results", [])
    total = data.get("total", len(results))
    succeeded = data.get("succeeded", len(results))
    header = format_text_header(
        status="ok",
        succeeded=succeeded,
        total=total,
        retried_count=_retried_count(results),
    )
    if not results:
        return header
    lines = [header, *(format_commit_line(r) for r in results)]
    return "\n".join(lines)


def _format_validation_reason(error: str) -> str:
    """Extract ``commit {N}: {reason}`` from a ``Commit {N}: ...`` error.

    For ``git add failed: {detail}`` errors, normalise the colon to an
    em-dash so the line reads ``commit N: git add failed — {detail}``.
    """
    rest = error[len("Commit ") :] if error.startswith("Commit ") else error
    colon = rest.find(":")
    if colon == -1:
        return f"commit {rest}"
    index_part = rest[:colon]
    reason = rest[colon + 1 :].lstrip()
    if reason.startswith("git add failed:"):
        detail = reason[len("git add failed:") :].lstrip()
        reason = f"git add failed — {detail}"
    return f"commit {index_part}: {reason}"


def _render_failed_commit(
    *,
    data: dict[str, Any],
    failed: dict[str, Any],
) -> str:
    """Render the M7 (pre-commit failed) failure branch."""
    results: list[dict[str, Any]] = data.get("results", [])
    succeeded = data.get("succeeded", len(results))
    total = data.get("total", succeeded + 1)
    index = failed.get("index", succeeded + 1)
    retried = bool(failed.get("retried"))
    extra = f"pre-commit failed at #{index}"
    if retried:
        extra += " (retried)"
    header = format_text_header(
        status="error",
        succeeded=succeeded,
        total=total,
        retried_count=_retried_count(results),
        extra=extra,
    )
    lines = [header]
    for r in results:
        lines.append(f"ok: {format_commit_line(r)}")
    lines.append(f"fail: {failed.get('message', '')}")
    auto_fixed = failed.get("auto_fixed_files") or []
    if auto_fixed:
        lines.append(f"auto-fixed: {', '.join(auto_fixed)}")
    output = (failed.get("precommit_output") or "").rstrip()
    if output:
        lines.append("hook output:")
        lines.extend(f"  {line}" for line in output.splitlines())
    return "\n".join(lines)


def _render_suggestions(
    *,
    error: str,
    suggestions: list[str],
) -> str:
    """Render the M4 (not-a-repo with child repos) failure branch."""
    header = format_text_header(
        status="error",
        succeeded=0,
        total=0,
        extra="not a git repository" if "not a git repository" in error else error,
    )
    hint = f"hint: child repos found — pass one as path: {', '.join(suggestions)}"
    return f"{header}\n{hint}"


def _render_validation(
    *,
    error: str,
    data: dict[str, Any],
) -> str:
    """Render the M5/M6 (validation / git add) failure branch."""
    results: list[dict[str, Any]] = data.get("results", [])
    succeeded = data.get("succeeded", len(results))
    total = data.get("total", succeeded + 1)
    header = format_text_header(
        status="error",
        succeeded=succeeded,
        total=total,
        retried_count=_retried_count(results),
    )
    return f"{header}\n{_format_validation_reason(error)}"


def render_failure_text(
    *,
    error: str,
    data: dict[str, Any] | None,
) -> str:
    """Render the failure-path text representation.

    Branches:

    - *data* is ``None``  → plain ``git_commit | error: {error}`` line.
    - *data* has ``suggestions``  → M4 not-a-repo hint.
    - *data* has ``failed_commit``  → M7 pre-commit failure with optional
      auto-fixed list and indented hook output.
    - otherwise  → M5/M6 validation or git-add failure.
    """
    if data is None:
        msg = error.lower() if error.startswith("No commits") else error
        return f"git_commit | error: {msg}"
    if data.get("suggestions"):
        return _render_suggestions(
            error=error,
            suggestions=list(data["suggestions"]),
        )
    failed = data.get("failed_commit")
    if failed is not None:
        return _render_failed_commit(data=data, failed=failed)
    return _render_validation(error=error, data=data)
