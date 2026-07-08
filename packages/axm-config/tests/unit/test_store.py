from __future__ import annotations

import pytest

from axm_config import ConfigError, set_


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
