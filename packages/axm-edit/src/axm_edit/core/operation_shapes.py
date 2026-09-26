"""Shared statement of the ``batch_edit`` operation shapes.

Single source of truth: the published hint is rendered from
:data:`OPERATION_EXAMPLES`, and a unit test parses every example through the
:data:`~axm_edit.models.operations.Operation` union, so the documented
shapes can never drift from the schema an agent is validated against.
"""

from __future__ import annotations

import json

__all__ = ["CHECKSUM_PLACEHOLDER", "OPERATION_EXAMPLES", "OPERATION_SHAPES_HINT"]

CHECKSUM_PLACEHOLDER: str = "<sha256 hex digest of the file bytes as read>"

OPERATION_EXAMPLES: tuple[dict[str, object], ...] = (
    {
        "op": "replace",
        "file": "pkg/mod.py",
        "edits": [
            {"old": "    return a", "new": "    return b"},
            {"old": "x = 1", "new": "x = 2", "line": 12},
        ],
    },
    {"op": "create", "file": "pkg/new.py", "content": "x = 1\n"},
    {"op": "delete", "file": "pkg/old.py"},
    {
        "op": "rewrite",
        "file": "pkg/mod.py",
        "content": "x = 2\n",
        "expected_checksum": CHECKSUM_PLACEHOLDER,
    },
)


def _render(examples: tuple[dict[str, object], ...]) -> str:
    """Render one JSON line per example under a short shape preamble.

    Args:
        examples: Operation examples, one per ``op`` kind.

    Returns:
        The hint text, without a trailing newline.
    """
    preamble = (
        "Operation shapes - `file` is relative to `path`, one replace op"
        " carries every edit of its file in `edits`, `line` is an optional"
        " 1-indexed search hint, and create accepts `overwrite: true`:"
    )
    lines = [f"- {json.dumps(example)}" for example in examples]
    return "\n".join([preamble, *lines])


OPERATION_SHAPES_HINT: str = _render(OPERATION_EXAMPLES)
