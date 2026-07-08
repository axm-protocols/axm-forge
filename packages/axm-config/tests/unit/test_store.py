from __future__ import annotations

import pytest

from axm_config import ConfigError, set_
from axm_config.store import _leaf_paths, _section


class _RecordingStore:
    """In-memory store that records every write (no real I/O)."""

    def __init__(self) -> None:
        self.writes: list[tuple[str, str, object]] = []
        self._data: dict[str, dict[str, object]] = {}

    def read(self, ns: str) -> dict[str, object]:
        return dict(self._data.get(ns, {}))

    def write(self, ns: str, key: str, value: object) -> None:
        self.writes.append((ns, key, value))
        self._data.setdefault(ns, {})[key] = value


@pytest.mark.parametrize("namespace", ["../evil", "a/b", "..", "", "a\\b", "a\x00b"])
def test_traversal_namespace_refused(
    namespace: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1, AC2: a traversal/empty/invalid namespace raises ConfigError.

    Validation happens at the public boundary before any write reaches the
    store, so no file can ever land outside ``~/.axm``. The store here is a
    recording in-memory stand-in (unit level, no real I/O): the assertion is
    that it never received the malicious write.
    """
    store = _RecordingStore()
    monkeypatch.setattr("axm_config.resolver._store", store)

    with pytest.raises(ConfigError):
        set_(namespace, "key", "value")

    assert store.writes == []


def test_section_excludes_child_namespace_subtables() -> None:
    """A nested table is a child namespace, not a key of the parent section.

    With ``[a]`` carrying ``x`` and a nested ``[a.b]`` table, ``_section`` for
    ``"a"`` must return only ``a``'s own scalar keys (``{'x': 1}``) -- the
    sub-table ``b`` is namespace ``a.b``, not a value of key ``b``. Regression
    for the dict-leak that made ``get('a', 'b')`` return a sub-table.
    """
    config = {"a": {"x": 1, "b": {"y": 2}}}

    assert _section(config, "a") == {"x": 1}
    assert _section(config, "a.b") == {"y": 2}


def test_leaf_paths_yields_mixed_parent_and_child() -> None:
    """A node that is both a namespace and a prefix yields *both* paths.

    ``[a]`` with a direct key ``x`` plus a nested ``[a.b]`` must enumerate both
    ``a`` and ``a.b`` -- the old leaf-only rule dropped ``a.b`` whenever the
    parent carried its own keys.
    """
    config = {"a": {"x": 1, "b": {"y": 2}}}

    assert sorted(_leaf_paths(config)) == ["a", "a.b"]


def test_leaf_paths_pure_nested_only_yields_children() -> None:
    """A pure-prefix table (no own keys) yields only its children."""
    config = {"storage": {"portfolio": {"team": "AXM"}}}

    assert _leaf_paths(config) == ["storage.portfolio"]
