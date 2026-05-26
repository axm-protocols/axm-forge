"""Compute tagged_plus_minus diffs between post-agent and post-lint snapshots."""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable

__all__ = ["compute_lint_diffs", "extract_rules_by_file"]

_DIAG_RE = re.compile(r"^(?P<file>[^:]+):\d+:\d+:\s+(?P<code>[A-Z]+\d+)\b")

# Ratio fallback only applies once the diff is large enough that re-reading
# the file becomes cheaper. Tiny diffs always surface verbatim.
_MIN_DIFF_FOR_RATIO = 100


def extract_rules_by_file(
    diagnostics: list[str],
    *,
    path_resolver: Callable[[str], str] | None = None,
) -> dict[str, list[str]]:
    """Parse ``file:line:col: CODE msg`` diagnostic lines into ``{file: [codes]}``.

    Args:
        diagnostics: Concise ruff diagnostic lines.
        path_resolver: Optional callable mapping raw file path to the key
            used by ``post_agent`` / ``post_lint`` (usually the relative path).
    """
    rules: dict[str, set[str]] = {}
    for line in diagnostics:
        match = _DIAG_RE.match(line)
        if match is None:
            continue
        file_key = match.group("file")
        if path_resolver is not None:
            file_key = path_resolver(file_key)
        rules.setdefault(file_key, set()).add(match.group("code"))
    return {f: sorted(codes) for f, codes in rules.items()}


def _tagged_plus_minus(pre: str, post: str) -> str:
    """Produce a compact diff with ``@L<n>`` hunk headers (1-indexed on pre).

    Consecutive non-equal opcodes are emitted with a single ``@L`` header
    anchored at the pre-line position of the hunk start.
    """
    pre_lines = pre.splitlines()
    post_lines = post.splitlines()
    matcher = difflib.SequenceMatcher(a=pre_lines, b=post_lines, autojunk=False)

    hunks: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        header = f"@L{i1 + 1}"
        parts: list[str] = [header]
        if tag in {"replace", "delete"}:
            parts.extend(f"-{line}" for line in pre_lines[i1:i2])
        if tag in {"replace", "insert"}:
            parts.extend(f"+{line}" for line in post_lines[j1:j2])
        hunks.append("\n".join(parts))

    return "\n".join(hunks)


def compute_lint_diffs(
    post_agent: dict[str, str],
    post_lint: dict[str, str],
    rules_by_file: dict[str, list[str]],
    *,
    max_ratio: float = 0.5,
    max_chars: int = 4000,
) -> list[dict[str, object]]:
    """Compute per-file diffs between post-agent and post-lint snapshots.

    Returns one entry per file that was mutated by ruff/claude_fix. Files
    whose content is unchanged are omitted (no empty list entries).

    When the diff exceeds ``max_ratio * len(post_lint_content)`` OR
    ``max_chars``, the entry falls back to ``{"file", "rules",
    "diff_skipped": "file_reread_recommended"}`` without a ``diff`` key.
    """
    entries: list[dict[str, object]] = []
    for file_key in sorted(post_agent):
        pre = post_agent[file_key]
        post = post_lint.get(file_key, pre)
        if pre == post:
            continue

        raw_rules = rules_by_file.get(file_key, [])
        rules = sorted(set(raw_rules))

        diff = _tagged_plus_minus(pre, post)
        post_len = len(post)
        diff_len = len(diff)
        ratio_trip = (
            diff_len >= _MIN_DIFF_FOR_RATIO
            and post_len > 0
            and diff_len > max_ratio * post_len
        )
        chars_trip = diff_len > max_chars
        if ratio_trip or chars_trip:
            entries.append(
                {
                    "file": file_key,
                    "rules": rules,
                    "diff_skipped": "file_reread_recommended",
                }
            )
        else:
            entries.append(
                {
                    "file": file_key,
                    "rules": rules,
                    "diff": diff,
                }
            )
    return entries
