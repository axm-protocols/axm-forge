"""Unit tests for the factored echo waiver mechanism (AC3, AC4, AC5).

Ported contract from ``axm_audit.core.rules.test_quality.duplicate_tests``,
made parametrizable by key schema: echo hashes on ``(package, qualname)``,
duplicate_tests on ``(file, name)``.
"""

from __future__ import annotations

from axm_echo.waiver import (
    cluster_hash,
    mark_acknowledged,
    stale_acknowledged,
    validate_acknowledged_entry,
)


def _cluster(members: list[dict[str, str]]) -> dict[str, object]:
    """Build a minimal cluster dict carrying the given members."""
    return {"members": members}


def test_cluster_hash_order_independent() -> None:
    """AC3: cluster_hash is order-independent and emits a 12-hex string."""
    members = [
        {"package": "axm-foo", "qualname": "foo.alpha"},
        {"package": "axm-bar", "qualname": "bar.beta"},
        {"package": "axm-baz", "qualname": "baz.gamma"},
    ]
    key = ("package", "qualname")
    direct = cluster_hash(_cluster(members), key_fields=key)
    shuffled = cluster_hash(_cluster(list(reversed(members))), key_fields=key)

    assert direct == shuffled
    assert len(direct) == 12
    assert all(c in "0123456789abcdef" for c in direct)


def test_cluster_hash_key_fields_param() -> None:
    """AC3: the same cluster hashes differently under different key schemas."""
    members = [
        {
            "package": "axm-foo",
            "qualname": "foo.alpha",
            "file": "foo/a.py",
            "name": "alpha",
        },
        {
            "package": "axm-bar",
            "qualname": "bar.beta",
            "file": "bar/b.py",
            "name": "beta",
        },
    ]
    echo_hash = cluster_hash(_cluster(members), key_fields=("package", "qualname"))
    test_hash = cluster_hash(_cluster(members), key_fields=("file", "name"))

    assert echo_hash != test_hash


def test_mark_and_stale() -> None:
    """AC4, AC5: a matching waiver marks its cluster; an orphan is stale."""
    key = ("package", "qualname")
    live = _cluster([{"package": "axm-foo", "qualname": "foo.alpha"}])
    other = _cluster([{"package": "axm-bar", "qualname": "bar.beta"}])
    live["cluster_hash"] = cluster_hash(live, key_fields=key)
    other["cluster_hash"] = cluster_hash(other, key_fields=key)
    clusters = [live, other]

    waivers = [
        {"hash": str(live["cluster_hash"]), "reason": "parallel API, intended"},
        {"hash": "deadbeef0000", "reason": "no longer exists"},
    ]

    mark_acknowledged(clusters, waivers)
    stale = stale_acknowledged(clusters, waivers)

    assert live.get("acknowledged") is True
    assert other.get("acknowledged") is not True
    stale_hashes = {entry["hash"] for entry in stale}
    assert stale_hashes == {"deadbeef0000"}


def test_invalid_entry_graceful() -> None:
    """AC4: malformed waiver entries return an error message, never raise."""
    assert validate_acknowledged_entry({"hash": "abc", "reason": "x"}) is not None
    assert (
        validate_acknowledged_entry({"hash": "abcdef012345", "reason": ""}) is not None
    )
    assert validate_acknowledged_entry("not a table") is not None
    assert (
        validate_acknowledged_entry({"hash": "abcdef012345", "reason": "legit waiver"})
        is None
    )
