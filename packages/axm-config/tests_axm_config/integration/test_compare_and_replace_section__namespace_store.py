"""Atomic namespace compare-and-replace across processes and profiles."""

from __future__ import annotations

import pytest

from axm_config import ConfigError, NamespaceStore, profile_config_path

pytestmark = pytest.mark.integration


def test_cas_conflict_preserves_file_and_child_namespaces():
    store = NamespaceStore()
    store.write("profile.child", "keep", "yes")
    store.write("profile", "revision", "0")
    assert store.compare_and_replace_section(
        "profile", {"revision": "1", "city": "Lyon"}, expected={"revision": "0"}
    )
    before = profile_config_path().read_bytes()
    assert not store.compare_and_replace_section(
        "profile", {"revision": "2"}, expected={"revision": "0"}
    )
    assert profile_config_path().read_bytes() == before
    assert store.read_exact("profile.child") == {"keep": "yes"}
    store.delete("profile", "city")
    store.delete("profile", "revision")
    assert store.read_exact("profile.child") == {"keep": "yes"}


def test_cas_migrates_legacy_while_preserving_unrelated_sections():
    store = NamespaceStore()
    store.write("other", "keep", 7)
    path = profile_config_path()
    legacy = path.parent / "profile.toml"
    legacy.write_text('revision = "0"\ncity = "Paris"\n')
    assert store.compare_and_replace_section(
        "profile",
        {"revision": "1", "city": "Lyon"},
        expected={"revision": "0", "city": "Paris"},
    )
    assert not legacy.exists()
    assert store.read_exact("other") == {"keep": 7}


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("operation", ["cas", "write", "delete", "replace"])
def test_all_mutators_refuse_corrupt_config_without_data_loss(legacy, operation):
    store = NamespaceStore()
    path = profile_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    corrupt = path.parent / "profile.toml" if legacy else path
    corrupt.write_bytes(b"invalid = [")
    before = corrupt.read_bytes()
    with pytest.raises(ConfigError):
        if operation == "cas":
            store.compare_and_replace_section("profile", {"revision": "1"}, expected={})
        elif operation == "write":
            store.write("profile", "revision", "1")
        elif operation == "delete":
            store.delete("profile", "revision")
        else:
            store.replace_section("profile", {"revision": "1"})
    assert corrupt.read_bytes() == before


def test_profiles_have_independent_locks_and_values(monkeypatch):
    store = NamespaceStore()
    monkeypatch.setenv("AXM_PROFILE", "first")
    assert store.compare_and_replace_section("profile", {"revision": "a"}, expected={})
    first = profile_config_path()
    monkeypatch.setenv("AXM_PROFILE", "second")
    assert store.compare_and_replace_section("profile", {"revision": "b"}, expected={})
    second = profile_config_path()
    assert first != second
    assert first.parent != second.parent
    assert store.read_exact("profile") == {"revision": "b"}
    monkeypatch.setenv("AXM_PROFILE", "first")
    assert store.read_exact("profile") == {"revision": "a"}


def test_profile_is_captured_before_lock_and_entire_mutation(monkeypatch):
    from axm_config.store import _PinnedNamespaceStore

    monkeypatch.setenv("AXM_PROFILE", "first")
    first = profile_config_path()
    load = _PinnedNamespaceStore._load_for_update

    def switch_after_lock(store):
        monkeypatch.setenv("AXM_PROFILE", "second")
        return load(store)

    monkeypatch.setattr(_PinnedNamespaceStore, "_load_for_update", switch_after_lock)
    assert NamespaceStore().compare_and_replace_section(
        "profile", {"revision": "a"}, expected={}
    )
    second = profile_config_path()
    assert first.is_file()
    assert not second.exists()
