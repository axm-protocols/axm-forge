"""Shared helpers for ``tests/unit``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.unit._helpers import <name>``.
"""

from __future__ import annotations

import json


def _fixture_text() -> str:
    payload = {
        "users": [
            {"id": i, "name": f"user_{i}", "active": True, "notes": None}
            for i in range(20)
        ],
        "meta": {"version": 1, "description": "   spaced   text   "},
    }
    return json.dumps(payload, indent=2)
