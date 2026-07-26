"""Compute tagged_plus_minus diffs between post-agent and post-lint snapshots."""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass

__all__ = [
    "ImportRemoval",
    "compute_lint_diffs",
    "extract_import_removals",
    "extract_rules_by_file",
]

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


_DANGEROUS_CODES = frozenset({"F401", "F811"})

# Isolates the file, ruff code and the back-quoted symbol name from a concise
# diagnostic line, e.g. ``mod.py:1:8: F401 [*] `os` imported but unused``.
_REMOVAL_RE = re.compile(
    r"^(?P<file>[^:]+):\d+:\d+:\s+(?P<code>[A-Z]+\d+)\b[^`]*(?:`(?P<name>[^`]+)`)?"
)


@dataclass(frozen=True, slots=True)
class ImportRemoval:
    """A dangerous ruff removal surfaced from a lint diff.

    ``F401`` marks an unused import ruff deleted; ``F811`` marks a symbol whose
    redefinition ruff dropped. ``name`` is the import/symbol identifier, ``file``
    the (optionally resolved) path and ``code`` the ruff rule that fired.
    """

    name: str
    file: str
    code: str


def extract_import_removals(
    diagnostics: list[str],
    *,
    path_resolver: Callable[[str], str] | None = None,
) -> dict[str, list[ImportRemoval]]:
    """Filter dangerous F401/F811 removals out of concise ruff diagnostics.

    Reuses :func:`extract_rules_by_file` as the authority on which
    ``(file, code)`` pairs ruff reported, then enriches each F401/F811 entry
    with the back-quoted symbol name from the diagnostic message. Pure: no I/O,
    no ruff re-run — it only classifies the already-collected diagnostics.

    Args:
        diagnostics: Concise ruff diagnostic lines (same input as
            :func:`extract_rules_by_file`).
        path_resolver: Optional callable mapping raw file path to the key used
            by ``post_agent`` / ``post_lint`` (usually the relative path).

    Returns:
        ``{file: [ImportRemoval, ...]}`` restricted to F401/F811 removals.
        Empty when no such removal is present.
    """
    rules_by_file = extract_rules_by_file(diagnostics, path_resolver=path_resolver)
    removals: dict[str, list[ImportRemoval]] = {}
    for line in diagnostics:
        match = _REMOVAL_RE.match(line)
        if match is None:
            continue
        code = match.group("code")
        if code not in _DANGEROUS_CODES:
            continue
        file_key = match.group("file")
        if path_resolver is not None:
            file_key = path_resolver(file_key)
        if code not in rules_by_file.get(file_key, []):
            continue
        name = match.group("name") or ""
        removals.setdefault(file_key, []).append(
            ImportRemoval(name=name, file=file_key, code=code)
        )
    return removals


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

    Returns one entry per file that was mutated by ruff/harness_fix. Files
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
