from __future__ import annotations

import pytest

from axm_config import ConfigError, set_
from axm_config.store import _raw_node, _with_child_tables


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


def test_raw_node_keeps_child_subtables() -> None:
    """`_raw_node` returns the ns node verbatim, child sub-tables included."""
    config: dict[str, object] = {
        "git": {"token": "abc", "default": {"name": "gabriel"}}
    }

    assert _raw_node(config, "git") == {
        "token": "abc",
        "default": {"name": "gabriel"},
    }


def test_raw_node_walks_dotted_namespace() -> None:
    """`_raw_node` walks a dotted ns down to the nested child table."""
    config: dict[str, object] = {"git": {"default": {"name": "gabriel"}}}

    assert _raw_node(config, "git.default") == {"name": "gabriel"}


def test_raw_node_missing_segment_returns_empty() -> None:
    """`_raw_node` returns `{}` when a namespace segment is absent."""
    config: dict[str, object] = {"git": {"token": "abc"}}

    assert _raw_node(config, "nope") == {}
    assert _raw_node(config, "git.missing") == {}


def test_raw_node_non_table_node_returns_empty() -> None:
    """`_raw_node` returns `{}` when the resolved node is not a table."""
    config: dict[str, object] = {"git": "not-a-table"}

    assert _raw_node(config, "git") == {}


def test_with_child_tables_preserves_absent_children() -> None:
    """Child sub-tables absent from `section` are re-attached, not dropped."""
    config: dict[str, object] = {
        "git": {"token": "old", "default": {"name": "gabriel"}}
    }

    merged = _with_child_tables(config, "git", {"token": "new"})

    assert merged == {"token": "new", "default": {"name": "gabriel"}}


def test_with_child_tables_section_overrides_same_named_child() -> None:
    """A `section` key wins over a preserved child sharing its name."""
    config: dict[str, object] = {"git": {"default": {"name": "old"}}}

    merged = _with_child_tables(config, "git", {"default": {"name": "new"}})

    assert merged == {"default": {"name": "new"}}


def test_with_child_tables_no_children_returns_section() -> None:
    """With no child sub-tables under ns, the result equals `section`."""
    config: dict[str, object] = {"git": {"token": "abc"}}
    section = {"token": "abc", "url": "https://example"}

    assert _with_child_tables(config, "git", section) == section
