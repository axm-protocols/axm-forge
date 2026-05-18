"""Shared helpers for ``tests/unit``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.unit._helpers import <name>``.
"""

from __future__ import annotations

from _registry_helpers import (
    build_rule_category_map,
)

_RULE_CATEGORY = build_rule_category_map()
