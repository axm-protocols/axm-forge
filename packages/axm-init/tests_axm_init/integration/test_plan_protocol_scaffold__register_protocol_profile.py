from __future__ import annotations

import threading
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from axm_init.core import protocol_scaffolder
from axm_init.core.protocol_scaffolder import (
    ProtocolScaffoldRequest,
    preview_protocol_scaffold,
)
from axm_init.models.protocol_scaffold import ProtocolScaffoldDecl


def _root(parent: Path, name: str) -> Path:
    root = parent / name
    root.mkdir()
    (root / "pyproject.toml").write_text(
        # Ownership is a package-creation decision, so every root used by
        # these application contracts declares its profile from the start.
        '[project]\nname = "example"\nversion = "0.1.0"\n'
        '\n[tool.axm-init.protocols]\nschema_version = 1\ndomain = "dev"\n',
        encoding="utf-8",
    )
    return root


def _request(action: str) -> ProtocolScaffoldRequest:
    declaration = ProtocolScaffoldDecl(
        domain="dev",
        unit="work",
        action=action,
        contracts=[],
        nodes=[],
    )
    return ProtocolScaffoldRequest(
        profile="protocols",
        domain="dev",
        unit="work",
        protocols=(declaration,),
        preview=False,
    )


def _actions(root: Path) -> set[str]:
    document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    units = document["tool"]["axm-init"]["protocols"]["units"]
    return {protocol["action"] for unit in units for protocol in unit["protocols"]}


@pytest.mark.integration
def test_same_root_applications_cannot_lose_metadata_declarations(
    tmp_path: Path,
    mocker,
) -> None:
    """AC1: same-root applications preserve both compatible declarations."""
    root = _root(tmp_path, "target")
    original_apply = protocol_scaffolder._apply_protocol_plan
    second_preflighted = threading.Event()
    counter_lock = threading.Lock()
    calls = 0

    def apply_after_preflight(*args, **kwargs) -> None:
        nonlocal calls
        with counter_lock:
            calls += 1
            position = calls
        if position == 1:
            second_preflighted.wait(timeout=0.25)
        else:
            second_preflighted.set()
        original_apply(*args, **kwargs)

    mocker.patch.object(
        protocol_scaffolder,
        "_apply_protocol_plan",
        side_effect=apply_after_preflight,
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(
            executor.submit(preview_protocol_scaffold, root, _request(action))
            for action in ("create", "exec")
        )
        errors = []
        for future in futures:
            try:
                future.result(timeout=2)
            except Exception as exc:
                errors.append(str(exc))

    explicit_conflict = bool(errors) and all(
        "occupied-incompatible" in error for error in errors
    )
    assert _actions(root) == {"create", "exec"} or explicit_conflict


@pytest.mark.integration
def test_failed_application_releases_its_root_lock(
    tmp_path: Path,
    mocker,
) -> None:
    """AC2: a failure releases the root lock for the next application."""
    root = _root(tmp_path, "target")
    original_apply = protocol_scaffolder._apply_protocol_plan
    first_entered = threading.Event()
    second_entered = threading.Event()
    release_failure = threading.Event()
    counter_lock = threading.Lock()
    calls = 0

    def fail_first_application(*args, **kwargs) -> None:
        nonlocal calls
        with counter_lock:
            calls += 1
            position = calls
        if position == 1:
            first_entered.set()
            assert release_failure.wait(timeout=2)
            raise RuntimeError("injected application failure")
        second_entered.set()
        original_apply(*args, **kwargs)

    mocker.patch.object(
        protocol_scaffolder,
        "_apply_protocol_plan",
        side_effect=fail_first_application,
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        failed = executor.submit(
            preview_protocol_scaffold,
            root,
            _request("create"),
        )
        assert first_entered.wait(timeout=1)
        later = executor.submit(
            preview_protocol_scaffold,
            root,
            _request("exec"),
        )
        entered_before_failure_cleanup = second_entered.wait(timeout=0.25)
        release_failure.set()
        with pytest.raises(RuntimeError, match="injected application failure"):
            failed.result(timeout=2)
        later.result(timeout=2)

    assert not entered_before_failure_cleanup
    assert _actions(root) == {"exec"}


@pytest.mark.integration
def test_distinct_roots_do_not_share_an_application_lock(
    tmp_path: Path,
    mocker,
) -> None:
    """AC3: distinct roots write concurrently while a canonical alias waits."""
    root_a = _root(tmp_path, "target-a")
    root_b = _root(tmp_path, "target-b")
    alias_a = tmp_path / "target-a-alias"
    alias_a.symlink_to(root_a, target_is_directory=True)

    original_apply = protocol_scaffolder._apply_protocol_plan
    first_a_entered = threading.Event()
    alias_a_entered = threading.Event()
    root_b_entered = threading.Event()
    release_writes = threading.Event()
    counter_lock = threading.Lock()
    root_a_calls = 0

    def hold_write_phases(root, *args, **kwargs) -> None:
        nonlocal root_a_calls
        canonical_root = root.resolve()
        if canonical_root == root_a.resolve():
            with counter_lock:
                root_a_calls += 1
                position = root_a_calls
            if position == 1:
                first_a_entered.set()
            else:
                alias_a_entered.set()
        elif canonical_root == root_b.resolve():
            root_b_entered.set()
        assert release_writes.wait(timeout=2)
        original_apply(root, *args, **kwargs)

    mocker.patch.object(
        protocol_scaffolder,
        "_apply_protocol_plan",
        side_effect=hold_write_phases,
    )
    with ThreadPoolExecutor(max_workers=3) as executor:
        first_a = executor.submit(
            preview_protocol_scaffold,
            root_a,
            _request("create"),
        )
        assert first_a_entered.wait(timeout=1)
        same_canonical_root = executor.submit(
            preview_protocol_scaffold,
            alias_a,
            _request("exec"),
        )
        distinct_root = executor.submit(
            preview_protocol_scaffold,
            root_b,
            _request("create"),
        )
        distinct_entered_while_a_held = root_b_entered.wait(timeout=1)
        alias_entered_while_a_held = alias_a_entered.wait(timeout=0.25)
        release_writes.set()
        outcomes: list[Exception | None] = []
        for future in (first_a, same_canonical_root, distinct_root):
            try:
                future.result(timeout=2)
                outcomes.append(None)
            except Exception as exc:
                outcomes.append(exc)

    assert distinct_entered_while_a_held
    assert not alias_entered_while_a_held
    assert outcomes == [None, None, None]
