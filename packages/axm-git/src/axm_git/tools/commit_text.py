"""Text renderers for GitCommitTool dual-format ToolResult.

These helpers transform the structured ``data`` dict produced by
:class:`axm_git.tools.commit.GitCommitTool` into a compact, token-efficient
text representation suitable for MCP consumers.

The header pattern follows the AXM convention
(see ``axm_ast.tools.search_text``)::

    git_commit | {status} | {succeeded}/{total} commits [· {extra}]
"""

from __future__ import annotations

__all__ = [
    "format_commit_line",
    "format_text_header",
    "render_failure_text",
    "render_text",
]


def _as_int(value: object, default: int) -> int:
    """Narrow *value* to ``int`` (heterogeneous ``dict[str, object]`` payload)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _as_str(value: object, default: str = "") -> str:
    """Narrow *value* to ``str`` (heterogeneous ``dict[str, object]`` payload)."""
    return value if isinstance(value, str) else default


def _as_str_list(value: object) -> list[str]:
    """Narrow *value* to ``list[str]`` (heterogeneous ``dict[str, object]`` payload)."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _as_results(value: object) -> list[dict[str, object]]:
    """Narrow *value* to a list of result dicts."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


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


def format_commit_line(result: dict[str, object]) -> str:
    """Format one successful commit record as ``{sha} [↻ ]{message}``."""
    sha = _as_str(result.get("sha"))
    message = _as_str(result.get("message"))
    if result.get("retried"):
        return f"{sha} ↻ {message}"
    return f"{sha} {message}"


def _retried_count(results: list[dict[str, object]]) -> int:
    """Count entries in *results* that were retried after a hook auto-fix."""
    return sum(1 for r in results if r.get("retried"))


def render_text(data: dict[str, object]) -> str:
    """Render the success-path ``data`` dict.

    Header + one ``format_commit_line`` per entry in ``data['results']``.
    """
    results = _as_results(data.get("results"))
    total = _as_int(data.get("total"), len(results))
    succeeded = _as_int(data.get("succeeded"), len(results))
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
    data: dict[str, object],
    failed: dict[str, object],
) -> str:
    """Render the M7 (pre-commit failed) failure branch."""
    results = _as_results(data.get("results"))
    succeeded = _as_int(data.get("succeeded"), len(results))
    total = _as_int(data.get("total"), succeeded + 1)
    index = _as_int(failed.get("index"), succeeded + 1)
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
    lines.append(f"fail: {_as_str(failed.get('message'))}")
    auto_fixed = _as_str_list(failed.get("auto_fixed_files"))
    if auto_fixed:
        lines.append(f"auto-fixed: {', '.join(auto_fixed)}")
    output = _as_str(failed.get("precommit_output")).rstrip()
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
    data: dict[str, object],
) -> str:
    """Render the M5/M6 (validation / git add) failure branch."""
    results = _as_results(data.get("results"))
    succeeded = _as_int(data.get("succeeded"), len(results))
    total = _as_int(data.get("total"), succeeded + 1)
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
    data: dict[str, object] | None,
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
    suggestions = _as_str_list(data.get("suggestions"))
    if suggestions:
        return _render_suggestions(error=error, suggestions=suggestions)
    failed = data.get("failed_commit")
    if isinstance(failed, dict):
        return _render_failed_commit(data=data, failed=failed)
    return _render_validation(error=error, data=data)
