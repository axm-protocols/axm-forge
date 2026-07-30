from __future__ import annotations

import pytest

from axm_config import delete, get, set_

pytestmark = pytest.mark.integration


def test_delete_then_resolves_default() -> None:
    """AC4, AC5: delete removes the key, then get falls back to the default.

    Round-trips through the real ``~/.axm/<ns>.toml`` store (HOME redirected to
    a tmp dir by the autouse ``_isolated_home`` fixture).
    """
    set_("demo", "token", "secret")
    assert get("demo", "token", default="fallback") == "secret"

    delete("demo", "token")

    assert get("demo", "token", default="fallback") == "fallback"


def test_delete_absent_key_is_noop() -> None:
    """AC4: deleting an absent key is a silent no-op (no raise)."""
    delete("demo", "never_set")

    assert get("demo", "never_set", default="fallback") == "fallback"
