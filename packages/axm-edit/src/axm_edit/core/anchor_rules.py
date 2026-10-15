"""Shared statement of the ``batch_edit`` anchor contract.

Single source of truth: both tool agent hints and the ``batch_edit``
docstring compose :data:`ANCHOR_RULES_HINT`, so the published texts can
never drift apart.
"""

from __future__ import annotations

__all__ = ["ANCHOR_RULES_HINT"]

ANCHOR_RULES_HINT: str = (
    "Anchor rules for the `old` side of a replace edit:\n"
    "1. No trailing newline: `old` and `new` must not end with a newline,"
    " the line break belongs to the file and not to the anchor.\n"
    "2. Whole line for multi-line anchors: a multi-line `old` must start"
    " at the beginning of its first line and end at the end of its last"
    " line, partial first or last lines are refused.\n"
    "3. Indentation is kept: the leading whitespace is part of the line,"
    " copy it verbatim in both `old` and `new`.\n"
    "Syntax gate: a batch that would leave a parseable Python, TOML or JSON file"
    " unparseable is refused before any write. New Python and TOML files must"
    " parse; JSON comments and trailing commas are tolerated; new JSON files"
    " are unchecked.\n"
    "Authoring: anchor on code lines rather than prose, prefer the"
    " smallest single-line anchor that is unique in the file,"
    " and prefer several small anchored edits over one large multi-line"
    " anchor."
)
