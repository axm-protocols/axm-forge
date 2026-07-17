from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from axm_config import ConfigError, set_
from axm_config.store import (
    CONFIG_FILENAME,
    NamespaceStore,
    _raw_node,
    _with_child_tables,
)


def _seed_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``~/.axm`` at ``tmp_path`` and return the created home dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    home = tmp_path / ".axm"
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return home


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


def test_write_leaves_foreign_toml_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1: a foreign ``~/.axm/*.toml`` survives a write() on another namespace.

    A top-level ``.toml`` whose stem is not a valid namespace (here a hyphen
    makes it fail ``_NAMESPACE_RE``) is owned by another tool; ``write`` must
    never fold or unlink it.
    """
    home = _seed_home(tmp_path, monkeypatch)
    foreign = home / "mail-agent.toml"
    foreign.write_text('token = "keep-me"\n', encoding="utf-8")

    set_("portfolio", "risk", "high")

    assert foreign.exists()
    assert foreign.read_text(encoding="utf-8") == 'token = "keep-me"\n'


def test_namespaces_excludes_foreign_toml_stems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: namespaces() reports only ``_NAMESPACE_RE``-valid legacy stems."""
    home = _seed_home(tmp_path, monkeypatch)
    (home / CONFIG_FILENAME).write_text(
        '[portfolio]\nrisk = "high"\n', encoding="utf-8"
    )
    (home / "notes.toml").write_text("x = 1\n", encoding="utf-8")
    (home / "my-notes.toml").write_text("x = 1\n", encoding="utf-8")

    result = NamespaceStore().namespaces()

    assert "portfolio" in result
    assert "notes" in result
    assert "my-notes" not in result


def test_legacy_fold_ignores_non_namespace_stem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: write() neither unlinks nor folds a legacy file with a bad stem."""
    home = _seed_home(tmp_path, monkeypatch)
    foreign = home / "bad_stem.toml"
    foreign.write_text('old_key = "old"\n', encoding="utf-8")

    NamespaceStore().write("bad_stem", "new_key", "new")

    assert foreign.exists()
    config = tomllib.loads((home / CONFIG_FILENAME).read_text(encoding="utf-8"))
    assert "old_key" not in config.get("bad_stem", {})
