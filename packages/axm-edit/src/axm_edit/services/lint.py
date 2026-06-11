"""Harness auto-fix for remaining ruff errors.

After ``ruff --fix`` resolves what it can, this module runs an
axm-harness adapter (``codex-sdk`` by default, ``claude-agent-sdk``
fallback) to attempt fixing the remaining diagnostics — one call per
file (parallel), max one retry cycle.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from axm_harness.core.base import AdapterName, HarnessAdapter, HarnessRun

logger = logging.getLogger(__name__)

__all__ = ["harness_fix"]


# ─────────────────────────────────────────────────────────────────────────────
# Optional axm-harness integration
#
# axm-harness powers the LLM ruff auto-fix step. It lives in the sibling
# axm-cortex workspace and is not published to PyPI, so it is an optional
# extra (``axm-edit[harness]``). When absent, ``harness_fix`` degrades to a
# no-op: it logs a warning and returns the ruff errors unchanged.
#
# The symbols below are resolved lazily at call time. They remain module-level
# attributes so they can be monkeypatched in tests.
# ─────────────────────────────────────────────────────────────────────────────


def get_adapter(name: AdapterName) -> HarnessAdapter:
    """Resolve a harness adapter, importing axm-harness lazily.

    Raises ``ImportError`` if the optional ``axm-edit[harness]`` extra is not
    installed, or a harness error (e.g. missing credentials). Patched in tests
    to avoid importing the SDK.
    """
    from axm_harness.core.factory import get_adapter as _get_adapter

    return _get_adapter(name)


async def run(
    adapter: HarnessAdapter, prompt: str, options: dict[str, object]
) -> HarnessRun:
    """Run a harness adapter, importing axm-harness lazily.

    Patched in tests. Only reached after :func:`get_adapter` succeeds, so
    axm-harness is guaranteed importable here.
    """
    from axm_harness.core.runner import run as _run

    return await _run(adapter, prompt, options)


def _harness_error() -> type[Exception]:
    """Return the harness base exception, or ``Exception`` if unavailable."""
    try:
        from axm_harness.core.errors import HarnessSDKError
    except ImportError:
        return Exception
    return cast("type[Exception]", HarnessSDKError)


_FIX_TIMEOUT = 60
_SNIPPET_CONTEXT = 5  # lines of context around each error
_MAX_FULL_FILE = 300  # files ≤ this many lines get full-file prompt

_DEFAULT_ADAPTER = "codex-sdk"
_FALLBACK_ADAPTER = "claude-agent-sdk"

_FIX_SYSTEM_PROMPT = (
    'Fix ruff errors. Return ONLY JSON: {"edits": [{old, new}, ...]}. '
    "No explanation.\n"
    "RULES:\n"
    "- NEVER create new function, class, or method definitions "
    "to silence F821/F822 (undefined name). An undefined name "
    "almost always means a rename was incomplete or an import "
    "was lost; fix the reference site, do not fabricate the "
    "missing symbol.\n"
    "- For F821 on a name that looks like a renamed identifier "
    "(e.g. `_foo` when `foo` exists, or vice versa), update the "
    "reference to match the existing definition.\n"
    "- For F822 (undefined name in __all__), remove the stale "
    "entry from __all__; do not add a fake definition.\n"
    "- If you cannot resolve an error without inventing code, "
    "return an empty array `[]` and let a human handle it."
)

# JSON Schema enforced on harness output. Some adapters drop this
# option (claude-agent-sdk), so ``parse_edits`` stays as the defensive
# parsing layer.
# OpenAI structured output requires a root "object" schema, so the edits
# array is wrapped under an "edits" key (claude-agent-sdk drops the schema
# and may still return a bare array — parse_edits accepts both shapes).
_EDITS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "edits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                },
                "required": ["old", "new"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["edits"],
    "additionalProperties": False,
}

# Tool availability — checked once at import time.
_has_ruff: bool = shutil.which("ruff") is not None


def _group_errors_by_file(errors: list[str]) -> dict[str, list[str]]:
    """Group ruff diagnostic lines by their source filename.

    Ruff format: ``file:line:col: CODE description``
    """
    grouped: dict[str, list[str]] = defaultdict(list)
    for err in errors:
        parts = err.split(":", 1)
        if parts:
            grouped[parts[0].strip()].append(err)
    return dict(grouped)


def find_header_end(all_lines: list[str]) -> int:
    """Return 0-indexed line number of first class/def at indent 0.

    If no class/def found, returns len(all_lines) (whole file is header).
    """
    for i, line in enumerate(all_lines):
        if re.match(r"^(class |def |async def )", line):
            return i
    return len(all_lines)


def _build_full_file_prompt(file_path: Path, file_errors: list[str]) -> str:
    """Build a prompt containing the entire file with line numbers."""
    all_lines = file_path.read_text().splitlines()
    numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(all_lines))
    error_block = "\n".join(file_errors)
    return (
        f"File: {file_path.name}\n\n"
        f"Ruff errors:\n{error_block}\n\n"
        f"Full file (with line numbers):\n{numbered}\n\n"
        f"Return ONLY a JSON array of edits. Each edit is an object with "
        f'"old" (exact text to find) and "new" (replacement text) keys.\n'
        f'Example: [{{"old": "except:\\n    pass", '
        f'"new": "except Exception:\\n    logging.exception(\\"Unexpected error\\")"}}]'
    )


def _extract_error_lines(file_errors: list[str]) -> list[int]:
    """Extract 1-indexed line numbers from ruff diagnostic strings."""
    lines: list[int] = []
    for err in file_errors:
        match = re.match(r"[^:]+:(\d+):", err)
        if match:
            lines.append(int(match.group(1)))
    return lines


def build_snippets(file_path: Path, file_errors: list[str]) -> str:
    """Build targeted code snippets around each error (±N lines context).

    For large files (> _MAX_FULL_FILE), prepends the file header (imports
    and module-level code before the first class/def) to ensure Claude
    always sees existing imports.
    """
    all_lines = file_path.read_text().splitlines()
    total = len(all_lines)
    error_lines = _extract_error_lines(file_errors)

    # Merge overlapping ranges
    ranges: list[tuple[int, int]] = []
    for line_no in sorted(set(error_lines)):
        start = max(0, line_no - 1 - _SNIPPET_CONTEXT)
        end = min(total, line_no - 1 + _SNIPPET_CONTEXT + 1)
        if ranges and start <= ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
        else:
            ranges.append((start, end))

    # Prepend header range for large files
    header_end = find_header_end(all_lines)
    if header_end > 0:
        header_range = (0, header_end)
        if ranges and header_range[1] >= ranges[0][0]:
            # Header overlaps with first snippet — merge
            ranges[0] = (0, max(ranges[0][1], header_end))
        else:
            ranges.insert(0, header_range)

    # Build snippet text with line numbers
    parts: list[str] = []
    for start, end in ranges:
        snippet_lines = [f"{i + 1}: {all_lines[i]}" for i in range(start, end)]
        parts.append("\n".join(snippet_lines))

    return "\n...\n".join(parts)


def build_prompt(file_path: Path, file_errors: list[str]) -> str:
    """Build a Claude prompt with error details and targeted snippets.

    Files ≤ _MAX_FULL_FILE lines get the full file content.
    Larger files get header + error snippets.
    """
    total_lines = len(file_path.read_text().splitlines())
    if total_lines <= _MAX_FULL_FILE:
        return _build_full_file_prompt(file_path, file_errors)
    error_block = "\n".join(file_errors)
    snippets = build_snippets(file_path, file_errors)
    return (
        f"File: {file_path.name}\n\n"
        f"Ruff errors:\n{error_block}\n\n"
        f"Code snippets (with line numbers):\n{snippets}\n\n"
        f"Return ONLY a JSON array of edits. Each edit is an object with "
        f'"old" (exact text to find) and "new" (replacement text) keys.\n'
        f'Example: [{{"old": "except:\\n    pass", '
        f'"new": "except Exception:\\n    logging.exception(\\"Unexpected error\\")"}}]'
    )


def parse_edits(output: str) -> list[dict[str, str]]:
    """Parse Claude's JSON output into a list of old/new edit pairs.

    Strips markdown code fences before parsing. Returns an empty list
    on any parse failure (graceful degradation).
    """
    text = output.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first line (```json or ```) and last line (```)
        if lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1])
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError, TypeError):
        return []
    if isinstance(data, dict):
        data = data.get("edits")
    if not isinstance(data, list):
        return []
    for entry in data:
        if not isinstance(entry, dict) or "old" not in entry or "new" not in entry:
            return []
    return data


_DEF_PATTERN = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+\w+", re.MULTILINE)


def fabricates_definition(edit: dict[str, str]) -> bool:
    """Return True if *edit* introduces a new ``def`` or ``class``.

    Catches the pathological case where Claude invents a stub function
    or class to silence an F821/F822 (undefined name) error instead of
    fixing the reference site.
    """
    old_defs = len(_DEF_PATTERN.findall(edit["old"]))
    new_defs = len(_DEF_PATTERN.findall(edit["new"]))
    return new_defs > old_defs


def apply_edits(file_path: Path, edits: list[dict[str, str]]) -> bool:
    """Apply old→new string replacements on file content.

    Returns True if at least one edit matched, False otherwise.
    Writes back only if at least one replacement was applied.
    """
    if not edits:
        return False
    content = file_path.read_text()
    # Normalize CRLF to LF for matching
    content = content.replace("\r\n", "\n")
    matched = False
    for edit in edits:
        old = edit["old"]
        new = edit["new"]
        if old in content:
            content = content.replace(old, new, 1)
            matched = True
    if matched:
        file_path.write_text(content)
    return matched


_RUFF_NOISE_PREFIXES = ("Found ", "[*] ", "No fixes")


def filter_ruff_lines(stdout: str) -> list[str]:
    """Keep real diagnostic lines, dropping ruff summary noise."""
    return [
        line
        for line in stdout.strip().splitlines()
        if line.strip() and not line.startswith(_RUFF_NOISE_PREFIXES)
    ]


def _run_ruff_check(root: Path, files: list[str]) -> list[str]:
    """Run ruff check on specific files, return remaining diagnostics."""
    if not _has_ruff:
        return []
    str_files = [str(root / f) for f in files]
    try:
        result = subprocess.run(
            [
                "ruff",
                "check",
                "--output-format=concise",
                "--extend-select",
                "I",
                *str_files,
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []
    # Exit code 2+ = internal ruff error (AC5) — skip gracefully.
    if result.returncode > 1:
        return []
    if result.returncode != 0 and result.stdout.strip():
        return filter_ruff_lines(result.stdout)
    return []


def _resolve_adapter() -> HarnessAdapter | None:
    """Resolve the harness adapter, lazily and gracefully.

    ``AXM_EDIT_FIX_ADAPTER`` overrides the default (``codex-sdk``); on
    failure (missing credentials, missing SDK, unknown name) the
    resolver falls back to ``claude-agent-sdk``, then gives up.
    """
    configured = os.environ.get("AXM_EDIT_FIX_ADAPTER", _DEFAULT_ADAPTER)
    candidates = [configured]
    if _FALLBACK_ADAPTER not in candidates:
        candidates.append(_FALLBACK_ADAPTER)
    harness_error = _harness_error()
    for name in candidates:
        try:
            return get_adapter(cast("AdapterName", name))
        except (harness_error, ImportError) as exc:
            logger.debug("harness adapter %s unavailable: %s", name, exc)
    return None


def _call_harness(
    adapter: HarnessAdapter,
    root: Path,
    prompt: str,
    filename: str,
) -> tuple[str | None, str | None]:
    """Run the harness adapter and return ``(output, warning)``.

    ``warning`` is set on failure; ``output`` is ``None`` in that case.
    """
    options: dict[str, object] = {
        "system_prompt": _FIX_SYSTEM_PROMPT,
        "cwd": str(root),
        "response_schema": _EDITS_SCHEMA,
    }
    model = os.environ.get("AXM_EDIT_FIX_MODEL")
    if model:
        options["model"] = model
    try:
        result = asyncio.run(
            asyncio.wait_for(run(adapter, prompt, options), timeout=_FIX_TIMEOUT)
        )
    except TimeoutError:
        return None, f"harness timed out fixing {filename}"
    except _harness_error() as exc:
        return None, f"harness unavailable for {filename}: {exc}"
    return result.output, None


def _fabrication_warning(edits: list[dict[str, str]], filename: str) -> str | None:
    """Return a warning if *edits* fabricate a definition, else ``None``."""
    fabricated = [e for e in edits if fabricates_definition(e)] if edits else []
    if not fabricated:
        return None
    return (
        f"claude tried to fabricate a definition in {filename} "
        f"(rejected {len(fabricated)} edit(s) — likely F821/F822 hallucination)"
    )


def _fix_single_file(
    root: Path,
    filename: str,
    file_errors: list[str],
    adapter: HarnessAdapter,
) -> tuple[list[str], list[str]]:
    """Attempt to fix errors in a single file via the harness adapter.

    Returns ``(remaining_errors, warnings)``.
    """
    file_path = root / filename
    if not file_path.is_file():
        return file_errors, []

    output, warning = _call_harness(
        adapter, root, build_prompt(file_path, file_errors), filename
    )
    if warning is not None:
        return file_errors, [warning]

    if not output or not output.strip():
        return file_errors, []

    edits = parse_edits(output)
    fabrication_warning = _fabrication_warning(edits, filename)
    if fabrication_warning is not None:
        return file_errors, [fabrication_warning]
    if not edits or not apply_edits(file_path, edits):
        return file_errors, []

    # Re-check with ruff to confirm fix is clean
    remaining = _run_ruff_check(root, [filename])
    return remaining, []


def harness_fix(
    root: Path,
    errors: list[str],
    *,
    warnings: list[str] | None = None,
) -> list[str]:
    """Use an axm-harness adapter to auto-fix remaining ruff errors.

    Groups errors by file and runs one harness call per file in
    parallel. Max one attempt per file — if the fix fails or produces
    invalid output, the original errors are returned.

    Args:
        root: Project root directory.
        errors: Ruff diagnostic lines (``file:line:col: CODE msg``).
        warnings: Optional list to collect warning messages into.

    Returns:
        List of remaining errors after attempted fixes. Empty if all fixed.
    """
    if not errors:
        return []

    adapter = _resolve_adapter()
    if adapter is None:
        if warnings is not None:
            warnings.append("no harness available, auto-fix skipped")
        return errors

    grouped = _group_errors_by_file(errors)
    remaining: list[str] = []

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                _fix_single_file, root, filename, file_errors, adapter
            ): filename
            for filename, file_errors in grouped.items()
        }
        for future in as_completed(futures):
            file_remaining, file_warnings = future.result()
            remaining.extend(file_remaining)
            if warnings is not None:
                warnings.extend(file_warnings)

    return remaining
