"""Complete persisted namespace reads at the real filesystem boundary."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
import tomli_w

import axm_config
from axm_config import ConfigError, NamespaceStore, UnsafeHomeError, get_file

pytestmark = pytest.mark.integration


def test_unknown_dotted_tables_do_not_fabricate_namespaces(store_root: Path) -> None:
    expected = {"own": 1, "bad.key": {"unknown": 2}, "tree": {"bad/key": {}}}
    _write(store_root / "config.toml", {"demo": expected})
    assert _snapshot() == expected


def test_sorted_parent_descendant_conflict(store_root: Path) -> None:
    _write(store_root / "config.toml", {"demo": {"own": 1}})
    _write(store_root / "demo.tree.branch.toml", {"a": {"value": "parent"}})
    _write(store_root / "demo.tree.branch.a.toml", {"value": "descendant"})
    expected = {"branch": {"a": {"value": "descendant"}}}
    assert get_file("demo", "tree") == expected
    assert _snapshot()["tree"] == expected


def test_sandbox_launch_profile_and_private_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from axm_config.sandbox import activate_sandbox, deactivate_sandbox

    launch_home = Path.home()
    launch_root = launch_home / ".axm" / "profiles" / "development"
    launch_root.mkdir(parents=True)
    _write(launch_root / "config.toml", {"demo": {"port": 9000}})
    sandbox_home = tmp_path / "sandbox-home"
    private_root = sandbox_home / ".axm" / "profiles" / "development"
    private_root.mkdir(parents=True)
    _write(private_root / "config.toml", {"demo": {"port": 8123}})
    monkeypatch.setenv("AXM_PROFILE", "development")
    sandbox = activate_sandbox(tmp_path / "session")
    monkeypatch.setenv("HOME", str(sandbox_home))
    try:
        assert get_file("demo", "port") == 8123
        assert _snapshot() == {"port": 8123}
    finally:
        deactivate_sandbox(sandbox)


def test_selected_legacy_escape_refused_before_open(
    store_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside.toml"
    _write(outside, {"port": 9000})
    (store_root / "demo.toml").symlink_to(outside)
    original = Path.open

    def capture(path, *args, **kwargs):
        assert path != outside, "Escaping legacy path was opened"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", capture)
    with pytest.raises(ValueError, match="out-of-home"):
        _snapshot()


def test_inventory_and_path_captured_once(
    store_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(store_root / "config.toml", {"demo": {"own": 1, "a": {}, "b": {}}})
    calls = {"path": 0, "inventory": 0}
    original_path = NamespaceStore._config_path
    original_glob = Path.glob

    def path(store):
        calls["path"] += 1
        return original_path(store)

    def glob(root, pattern):
        calls["inventory"] += 1
        return original_glob(root, pattern)

    monkeypatch.setattr(NamespaceStore, "_config_path", path)
    monkeypatch.setattr(Path, "glob", glob)
    assert _snapshot() == {"own": 1, "a": {}, "b": {}}
    assert calls == {"path": 1, "inventory": 1}


def _snapshot(namespace: str = "demo") -> dict[str, object]:
    function = getattr(axm_config, "get_file_namespace", None)
    assert callable(function), "Missing root-public complete file namespace API"
    return cast(Callable[[str], dict[str, object]], function)(namespace)


@pytest.fixture
def store_root() -> Path:
    root = Path.home() / ".axm"
    root.mkdir()
    return root


def _write(path: Path, values: dict[str, object]) -> None:
    path.write_bytes(tomli_w.dumps(values).encode())


def test_complete_unknown_empty_and_detached_tree(store_root: Path) -> None:
    expected = {
        "port": 8123,
        "unknown_scalar": "retained",
        "unknown_table": {"nested": [{"values": [1, 2]}]},
        "empty": {},
        "instances": {"gpu-main": {"port": 8124}},
    }
    _write(store_root / "config.toml", {"demo": expected})
    result = _snapshot()
    assert result == expected
    assert "get_file_namespace" in axm_config.__all__
    assert NamespaceStore().read("demo") == {"port": 8123, "unknown_scalar": "retained"}
    nested = result["unknown_table"]["nested"][0]["values"]
    nested.append(3)
    assert _snapshot() == expected
    assert get_file("demo", "instances") == expected["instances"]


def test_central_own_keys_do_not_merge_or_open_ignored_legacy(
    store_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(store_root / "config.toml", {"demo": {"port": 8123}})
    (store_root / "demo.toml").symlink_to(store_root.parent / "outside.toml")
    original = Path.open
    opened: list[str] = []

    def capture(path, *args, **kwargs):
        opened.append(path.name)
        assert path.name != "demo.toml", "Ignored legacy must never be read"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", capture)
    assert _snapshot() == {"port": 8123}
    assert opened == ["config.toml"]


def test_child_only_central_preserves_direct_legacy_dictionary(
    store_root: Path,
) -> None:
    _write(store_root / "config.toml", {"demo": {"instances": {"gpu": {"port": 8124}}}})
    _write(store_root / "demo.toml", {"instances": {"legacy": {"port": 8125}}})
    expected = get_file("demo", "instances")
    assert expected == {"legacy": {"port": 8125}}
    assert _snapshot() == {"instances": expected}


def test_descendants_and_direct_underscore_fallback(store_root: Path) -> None:
    _write(store_root / "config.toml", {"demo": {"port": 8123, "empty": {}}})
    _write(store_root / "demo.extra_args.toml", {"first": ["a", "b"]})
    _write(store_root / "demo.instances.z.toml", {"port": 8125})
    _write(store_root / "demo.instances.a.toml", {"port": 8124})
    expected = {
        "port": 8123,
        "empty": {},
        "extra_args": {"first": ["a", "b"]},
        "instances": {"a": {"port": 8124}, "z": {"port": 8125}},
    }
    assert _snapshot() == expected
    for key in expected:
        assert get_file("demo", key, default=object()) == expected[key]


def test_sorted_descendants_override_intermediate_scalars(store_root: Path) -> None:
    _write(store_root / "demo.tree.toml", {"branch": "legacy scalar"})
    _write(store_root / "demo.tree.branch.z.toml", {"last": 3})
    _write(store_root / "demo.tree.branch.a.toml", {"first": 1})
    expected = get_file("demo", "tree")
    assert expected == {"branch": {"a": {"first": 1}, "z": {"last": 3}}}
    assert _snapshot() == {"tree": expected}


@pytest.mark.parametrize("tombstone", [False, True])
def test_execution_overlay_matches_get_file(store_root: Path, tombstone: bool) -> None:
    namespace = "execution.review"
    token = b"review".hex()
    canonical = (
        {"tombstone": "v1"} if tombstone else {"backend": "canonical", "unknown": 4}
    )
    _write(
        store_root / "config.toml",
        {"execution": {"review": {"backend": "old"}, "v1": {token: canonical}}},
    )
    expected = {} if tombstone else canonical
    assert _snapshot(namespace) == expected
    for key in ("backend", "unknown"):
        sentinel = object()
        actual = get_file(namespace, key, default=sentinel)
        assert (key not in expected and actual is sentinel) or actual == expected[key]


def test_business_environment_ignored(
    store_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(store_root / "config.toml", {"demo": {"port": 8123}})
    monkeypatch.setenv("AXM_DEMO_PORT", "9999")
    monkeypatch.setenv("AXM_DEMO_UNKNOWN", "not persisted")
    assert _snapshot() == {"port": 8123}


def test_profile_captured_once_for_central_and_legacy(
    store_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(store_root / "config.toml", {"demo": {"port": 9000}})
    dev = store_root / "profiles" / "dev"
    dev.mkdir(parents=True)
    _write(dev / "config.toml", {"demo": {"port": 8123}})
    _write(dev / "demo.child.toml", {"value": "dev"})
    monkeypatch.setenv("AXM_PROFILE", "dev")
    original = Path.open
    opened: list[Path] = []

    def capture(path, *args, **kwargs):
        opened.append(path)
        result = original(path, *args, **kwargs)
        if path == dev / "config.toml":
            monkeypatch.setenv("AXM_PROFILE", "production")
        return result

    monkeypatch.setattr(Path, "open", capture)
    assert _snapshot() == {"port": 8123, "child": {"value": "dev"}}
    assert opened.count(dev / "config.toml") == 1
    assert opened.count(dev / "demo.child.toml") == 1
    assert all(path.parent == dev for path in opened)


def test_missing_named_profile_does_not_fall_back_or_create(
    store_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(store_root / "config.toml", {"demo": {"port": 9000}})
    monkeypatch.setenv("AXM_PROFILE", "absent")
    assert _snapshot() == {}
    assert not (store_root / "profiles").exists()


def test_read_counts_and_no_write(
    store_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(store_root / "config.toml", {"demo": {"own": 1}})
    _write(store_root / "demo.tree.toml", {"legacy": 2})
    _write(store_root / "demo.tree.a.toml", {"a": 3})
    before = {path: path.read_bytes() for path in store_root.iterdir()}
    original = Path.open
    opened: list[Path] = []

    def capture(path, *args, **kwargs):
        opened.append(path)
        assert not any(
            letter in (args[0] if args else kwargs.get("mode", "r"))
            for letter in "wax+"
        )
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", capture)
    assert _snapshot() == {"own": 1, "tree": {"legacy": 2, "a": {"a": 3}}}
    assert opened.count(store_root / "config.toml") == 1
    assert len(opened) == len(set(opened))
    monkeypatch.setattr(Path, "open", original)
    assert {path: path.read_bytes() for path in store_root.iterdir()} == before


@pytest.mark.parametrize("name", ["../bad", "Demo", "", "demo.bad/key", "demo..bad"])
def test_invalid_names_refused_without_io(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_open(*args, **kwargs):
        pytest.fail("Invalid namespace performed I/O")

    monkeypatch.setattr(Path, "open", no_open)
    with pytest.raises(ConfigError):
        _snapshot(name)


def test_unsafe_home_raises_existing_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(UnsafeHomeError):
        _snapshot()


@pytest.mark.parametrize("state", ["missing", "malformed", "unreadable"])
def test_missing_or_bad_files_degrade_without_creation(
    state: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = Path.home()
    if state != "missing":
        root = home / ".axm"
        root.mkdir()
        (root / "config.toml").write_text("[bad")
    if state == "unreadable":

        def denied(*args, **kwargs):
            raise PermissionError("synthetic denial")

        monkeypatch.setattr(Path, "open", denied)
    assert _snapshot() == {}
    if state == "missing":
        assert not (home / ".axm").exists()


def test_hostile_unknown_tables_are_data_not_paths(
    store_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = {"own": 1, "../../outside": {"unknown": 2}, "bad/name": {}}
    _write(store_root / "config.toml", {"demo": expected})
    original = Path.open
    opened: list[Path] = []

    def capture(path, *args, **kwargs):
        opened.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", capture)
    assert _snapshot() == expected
    assert opened == [store_root / "config.toml"]
