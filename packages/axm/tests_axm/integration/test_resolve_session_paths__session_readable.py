"""Session path normalization and retained read authority share one boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm.tools.dependency_reads import (
    DependencyEnvironment,
    current_read_contract,
    dependency_read_context,
    read_context_bound,
    resolve_read_path,
    restricted_read_context,
    session_dependencies,
    session_readable,
)
from axm.tools.session_paths import resolve_session_paths
from axm.tools.write_scope import WRITE_CONTRACT_ENV, WriteContract

pytestmark = pytest.mark.integration


def test_normalization_uses_the_session_root_and_preserves_nested_payloads(
    tmp_path: Path,
) -> None:
    """Defaults, nested file lists and operations resolve against the same root."""
    payload: dict[str, object] = {
        "path": "source",
        "files": [Path("a.py"), ["b.py", None, 7]],
        "operations": [{"op": "replace", "file": "c.py"}, {"op": "other"}, "opaque"],
        "mode": "relative-looking-value",
    }
    resolve_session_paths(
        payload,
        {"path": ".", "cwd": ".", "extra_dir": "data"},
        WriteContract(str(tmp_path)),
    )
    assert payload["path"] == str(tmp_path / "source")
    assert payload["cwd"] == str(tmp_path)
    assert payload["extra_dir"] == str(tmp_path / "data")
    assert payload["files"] == [
        tmp_path / "source/a.py",
        [str(tmp_path / "source/b.py"), None, 7],
    ]
    assert payload["operations"] == [
        {"op": "replace", "file": str(tmp_path / "source/c.py")},
        {"op": "other"},
        "opaque",
    ]
    assert payload["mode"] == "relative-looking-value"


@pytest.mark.parametrize("field", ["path", "file", "files"])
def test_unbound_relative_paths_are_refused(tmp_path: Path, field: str) -> None:
    """An absolute payload path alone cannot impersonate a bound execution root."""
    payload: dict[str, object] = {"path": str(tmp_path), field: "relative.py"}
    with pytest.raises(ValueError, match="relative paths require"):
        resolve_session_paths(payload, {}, None)


def test_unbound_absolute_paths_remain_absolute(tmp_path: Path) -> None:
    """Absolute requests are canonicalized without inventing a session root."""
    payload: dict[str, object] = {
        "path": str(tmp_path / "child" / ".."),
        "file": str(tmp_path / "child" / ".." / "a.py"),
    }
    resolve_session_paths(payload, {}, None)
    assert payload == {"path": str(tmp_path), "file": str(tmp_path / "a.py")}


def test_aliases_are_normalized_and_escaping_symlinks_are_refused(
    tmp_path: Path,
) -> None:
    """An alias must retain the canonical target's read boundary."""
    root = tmp_path / "session"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    alias = str(tmp_path / "service-checkout")
    contract = WriteContract(str(root), read_path_aliases=((alias, str(root)),))
    payload: dict[str, object] = {"file": f"{alias}/visible.py"}
    resolve_session_paths(payload, {}, contract)
    assert payload["file"] == str(root / "visible.py")
    for raw in (
        f"{alias}/escape/private.py",
        str(root / "escape/private.py"),
        "../outside",
    ):
        with pytest.raises(ValueError, match="path escapes"):
            resolve_session_paths({"path": raw}, {}, contract)


def test_binding_overrides_ambient_authority_and_restores_it_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit transport denial cannot fall back to a process environment."""
    monkeypatch.setenv(
        WRITE_CONTRACT_ENV, json.dumps({"execution_root": str(tmp_path)})
    )
    assert not read_context_bound()
    assert session_readable(tmp_path)
    with pytest.raises(RuntimeError, match="interrupted"):
        with dependency_read_context(None):
            assert read_context_bound()
            assert current_read_contract() is None
            assert not session_readable(tmp_path)
            assert session_dependencies().roots == ()
            raise RuntimeError("interrupted")
    assert not read_context_bound()
    assert session_readable(tmp_path)


def test_retained_authority_intersects_the_live_caller_and_restores_on_exit(
    tmp_path: Path,
) -> None:
    """Retaining a narrower origin cannot grant the caller's sibling roots."""
    allowed = tmp_path / "allowed"
    denied = tmp_path / "denied"
    allowed.mkdir()
    denied.mkdir()
    caller = WriteContract(str(tmp_path))
    origin = WriteContract(str(tmp_path), read_roots=(str(allowed),))
    with dependency_read_context(caller):
        with restricted_read_context(origin):
            assert read_context_bound()
            assert session_readable(allowed)
            assert not session_readable(denied)
            with restricted_read_context(None):
                assert current_read_contract() is None
        assert session_readable(denied)


def test_declared_dependency_reads_never_grant_writes(
    dependency_project: tuple[DependencyEnvironment, Path],
) -> None:
    """The dependency closure is readable while write grants remain project-local."""
    environment, api = dependency_project
    root = Path(environment.package_root)
    contract = WriteContract(
        str(root), allowed_prefixes=(str(root),), dependency_environment=environment
    )
    with dependency_read_context(contract):
        assert ("fixture_api", str(api)) in session_dependencies().roots
        assert session_readable(api / "types.py")
        assert resolve_read_path(root, str(api / "types.py")) == api / "types.py"
        assert not contract.permits(str(api / "types.py"))
        assert resolve_read_path(root, str(api.parent / "rogue")) is None
    with dependency_read_context(None):
        assert resolve_read_path(root, "local.py") == root / "local.py"
        assert resolve_read_path(root, str(api / "types.py")) is None
        assert session_dependencies().roots == ()
    with dependency_read_context(WriteContract(str(root))):
        assert session_dependencies().roots == ()
