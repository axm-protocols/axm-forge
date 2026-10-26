"""Text renderers for GitTagTool dual-format ToolResult.

Transform the structured ``data`` dict produced by
:class:`axm_git.tools.tag.GitTagTool` into a compact text representation::

    git_tag | ✓ | {tag} · {bump} [· breaking] · {n} commits · pushed
        · remote verified
    resolved {version} from git tag · commit {sha12} · CI {ci} · prev {tag}

    git_tag | ✗ | {error}
    [{full_tag} [@ {sha12}] kept locally · [not] pushed · remote unverified]

(The success header is a single line; it is wrapped here for width.)
"""

from __future__ import annotations

__all__ = ["render_failure_text", "render_text"]

_SHORT_SHA = 12


def _as_str(value: object, default: str = "") -> str:
    """Narrow *value* to ``str`` (heterogeneous ``dict[str, object]`` payload)."""
    return value if isinstance(value, str) else default


def _as_int(value: object, default: int = 0) -> int:
    """Narrow *value* to ``int`` (heterogeneous payload)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _as_str_list(value: object) -> list[str]:
    """Narrow *value* to ``list[str]`` (heterogeneous payload)."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def render_text(data: dict[str, object]) -> str:
    """Render the success-path ``data`` dict.

    Header carries tag, bump type, breaking flag, commit count, push status
    and remote verification; a second line carries the Git-derived version
    and its source (when available), the tagged commit, the CI status and the
    previous tag.
    """
    tag = _as_str(data.get("full_tag")) or _as_str(data.get("tag"))
    bump = _as_str(data.get("bump"))
    sections = [tag, bump]
    if data.get("breaking"):
        sections.append("breaking")
    sections.append(f"{_as_int(data.get('commits_included'))} commits")
    sections.append("pushed" if data.get("pushed") else "not pushed")
    if data.get("remote_verified"):
        sections.append("remote verified")
    header = f"git_tag | ✓ | {' · '.join(sections)}"

    detail: list[str] = []
    resolved = _as_str(data.get("resolved_version"))
    if resolved:
        source = _as_str(data.get("version_source"))
        detail.append(
            f"resolved {resolved} from git tag"
            if source == "git_tag"
            else f"resolved {resolved}"
        )
    commit = _as_str(data.get("tag_commit"))
    if commit:
        detail.append(f"commit {commit[:_SHORT_SHA]}")
    ci_check = _as_str(data.get("ci_check"))
    if ci_check:
        detail.append(f"CI {ci_check}")
    detail.append(f"prev {_as_str(data.get('current_tag'), 'none')}")
    return f"{header}\n{' · '.join(detail)}"


def _tag_state(data: dict[str, object]) -> str | None:
    """Describe the tag left behind by a post-creation failure, if any."""
    full_tag = _as_str(data.get("full_tag"))
    if not full_tag or "pushed" not in data:
        return None
    commit = _as_str(data.get("tag_commit"))
    where = f"{full_tag} @ {commit[:_SHORT_SHA]}" if commit else full_tag
    pushed = "pushed" if data.get("pushed") else "not pushed"
    remote = "remote verified" if data.get("remote_verified") else "remote unverified"
    return f"{where} kept locally · {pushed} · {remote}"


def _preflight_detail(data: dict[str, object]) -> str | None:
    """Describe a pre-creation failure (dirty tree, not-a-repo, no commits, CI)."""
    dirty = _as_str_list(data.get("dirty_files"))
    if dirty:
        return f"dirty: {', '.join(dirty)}"
    suggestions = _as_str_list(data.get("suggestions"))
    if suggestions:
        return f"hint: pass one as path: {', '.join(suggestions)}"
    current_tag = data.get("current_tag")
    if current_tag is not None:
        return f"prev {_as_str(current_tag, 'none')}"
    ci_check = data.get("ci_check")
    if ci_check is not None:
        return f"CI {_as_str(ci_check)}"
    return None


def render_failure_text(*, error: str, data: dict[str, object] | None) -> str:
    """Render the failure-path text representation.

    Surfaces the local tag state after a post-creation failure (verification,
    push or remote verification); otherwise ``dirty_files`` (uncommitted
    changes), ``suggestions`` (not-a-repo), ``current_tag`` (no commits since
    last tag) or ``ci_check`` (CI red) when present in *data*.
    """
    header = f"git_tag | ✗ | {error}"
    if data is None:
        return header
    detail = _tag_state(data) or _preflight_detail(data)
    return f"{header}\n{detail}" if detail else header
