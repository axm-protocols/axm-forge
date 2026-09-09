"""Integration contracts for applying protocol scaffold plans atomically."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any
from unittest.mock import patch

import pytest

from axm_init.core.framework import Framework
from axm_init.core.protocol_metadata import merge_protocol_metadata
from axm_init.core.protocol_planner import (
    PlanOperation,
    PlanStatus,
    ProtocolScaffoldPlan,
    plan_protocol_scaffold,
)
from axm_init.core.protocol_scaffolder import (
    ProtocolScaffoldRequest,
    prepare_protocol_request,
    preview_protocol_scaffold,
)
from axm_init.models.protocol_scaffold import ProtocolScaffoldDecl
from axm_init.tools.scaffold import InitScaffoldTool

IDENTITY = {
    "org": "test-org",
    "author": "Test Author",
    "email": "test@example.com",
}
DECLARATION: dict[str, object] = {
    "domain": "dev",
    "unit": "work",
    "action": "create",
    "contracts": [{"name": "brief"}],
    "prompts": [{"name": "author", "text": "Author the work."}],
    "nodes": [{"name": "author", "contract": "brief", "prompt": "author"}],
    "phases": [{"name": "draft", "nodes": ["author"]}],
    "ticket": {"ticket_type": "dev.work", "input_contract": "brief"},
}


def _metadata() -> str:
    return (
        "# project header\n"
        '[project]\nname = "protocols-dev" # package identity\n'
        'version = "0.1.0"\n\n'
        "[tool.unrelated]\n"
        "answer = 42 # keep inline\n"
    )


def _write_project(root: Path, metadata: str | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        metadata if metadata is not None else _metadata(),
        encoding="utf-8",
    )


def _declaration() -> ProtocolScaffoldDecl:
    return ProtocolScaffoldDecl.model_validate(DECLARATION)


def _request(*, preview: bool = False) -> ProtocolScaffoldRequest:
    request = prepare_protocol_request(
        profile="protocols",
        domain="dev",
        unit="work",
        protocols=[DECLARATION],
        preview=preview,
        framework=Framework.PYTHON,
    )
    assert isinstance(request, ProtocolScaffoldRequest)
    return request


def _file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _full_snapshot(root: Path) -> dict[str, tuple[str, bytes | str]]:
    snapshot: dict[str, tuple[str, bytes | str]] = {}
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in names:
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                snapshot[relative] = ("symlink", os.readlink(path))
            else:
                snapshot[relative] = ("dir", b"")
        for name in files:
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                snapshot[relative] = ("symlink", os.readlink(path))
            else:
                snapshot[relative] = ("file", path.read_bytes())
    return snapshot


def _apply(root: Path) -> Any:
    return preview_protocol_scaffold(root, _request(preview=False))


@pytest.mark.integration
def test_complete_plan_materializes_declared_creation_set_and_profile(
    tmp_path: Path,
) -> None:
    """AC2: applying a complete plan writes exactly its CREATE set and profile."""
    _write_project(tmp_path)
    initial_metadata = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    plan = plan_protocol_scaffold(_declaration(), initial_metadata, {})
    expected = {
        operation.path.as_posix()
        for operation in plan.operations
        if operation.status is PlanStatus.CREATE
    }

    result = _apply(tmp_path)

    assert result.success is True
    assert result.preview is False
    written = set(_file_bytes(tmp_path)) - {"pyproject.toml"}
    assert written == expected
    merged = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.axm-init.protocols]" in merged
    assert 'domain = "dev"' in merged


@pytest.mark.integration
def test_immediate_replay_is_idempotent_and_preserves_implemented_owned_file(
    tmp_path: Path,
) -> None:
    """AC3: replay reports owned files unchanged and preserves implementation bytes."""
    _write_project(tmp_path)
    first = _apply(tmp_path)
    assert first.success is True
    owned = tmp_path / "src/protocols_dev/work/create/protocol.py"
    implemented = owned.read_bytes() + b"\nIMPLEMENTED = True\n"
    owned.write_bytes(implemented)
    before = _file_bytes(tmp_path)

    replay = _apply(tmp_path)

    assert replay.success is True
    assert replay.created == []
    assert replay.updated == []
    assert set(replay.unchanged) == set(first.created)
    assert _file_bytes(tmp_path) == before
    assert owned.read_bytes() == implemented


@pytest.mark.integration
def test_dangerous_plans_fail_entirely_during_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: traversal, outward symlink, and occupied paths have distinct refusals."""
    outside = tmp_path / "outside"
    outside.mkdir()
    cases = (
        ("outside-root", PurePosixPath("../escape.py"), False),
        ("outward-symlink", PurePosixPath("linked/escape.py"), True),
        ("occupied-incompatible", PurePosixPath("occupied.py"), False),
    )
    for index, (reason, planned_path, needs_link) in enumerate(cases):
        root = tmp_path / f"case-{index}"
        _write_project(root)
        if needs_link:
            (root / "linked").symlink_to(outside, target_is_directory=True)
        if reason == "occupied-incompatible":
            (root / planned_path).write_bytes(b"user-owned\n")
        before = _full_snapshot(root)
        metadata = (root / "pyproject.toml").read_text(encoding="utf-8")
        malicious = ProtocolScaffoldPlan(
            operations=(
                PlanOperation(
                    path=planned_path,
                    status=PlanStatus.CREATE,
                    content="planned\n",
                ),
            ),
            metadata=metadata + '\n[tool.axm-init.protocols]\ndomain = "dev"\n',
        )
        monkeypatch.setattr(
            "axm_init.core.protocol_scaffolder.plan_protocol_scaffold",
            lambda *_ignored, plan=malicious: plan,
        )

        result = InitScaffoldTool().execute(
            path=str(root),
            profile="protocols",
            domain="dev",
            unit="work",
            protocols=[DECLARATION],
            preview=False,
            **IDENTITY,
        )

        assert result.success is False
        assert reason in (result.error or "")
        assert _full_snapshot(root) == before


@pytest.mark.integration
def test_failures_at_every_application_stage_roll_back_owned_mutations(
    tmp_path: Path,
) -> None:
    """AC5: write and metadata failures restore the exact pre-operation snapshot."""
    original_write_text = Path.write_text
    stages = ("before-first-write", "between-file-writes", "metadata-merge")

    calls = 0

    def failing_write_text(
        failure_stage: str,
    ) -> Callable[[Path, str, str | None, str | None, str | None], int]:
        def write_text(
            path: Path,
            data: str,
            encoding: str | None = None,
            errors: str | None = None,
            newline: str | None = None,
        ) -> int:
            nonlocal calls
            calls += 1
            should_fail = (
                (failure_stage == "before-first-write" and calls == 1)
                or (failure_stage == "between-file-writes" and calls == 2)
                or (failure_stage == "metadata-merge" and path.name == "pyproject.toml")
            )
            if should_fail:
                raise OSError(failure_stage)
            return original_write_text(
                path,
                data,
                encoding=encoding,
                errors=errors,
                newline=newline,
            )

        return write_text

    for index, stage in enumerate(stages):
        root = tmp_path / str(index)
        _write_project(root)
        marker = root / "keep.bin"
        marker.write_bytes(b"original\x00bytes")
        before = _full_snapshot(root)
        calls = 0

        with patch.object(
            Path,
            "write_text",
            new=failing_write_text(stage),
        ):
            result = InitScaffoldTool().execute(
                path=str(root),
                profile="protocols",
                domain="dev",
                unit="work",
                protocols=[DECLARATION],
                preview=False,
                **IDENTITY,
            )

        assert result.success is False
        assert stage in (result.error or "")
        assert _full_snapshot(root) == before


@pytest.mark.integration
def test_metadata_merge_retains_toml_presentation(tmp_path: Path) -> None:
    """AC6: applying the profile preserves existing TOML presentation exactly."""
    original = _metadata()
    _write_project(tmp_path, original)
    expected_merge = merge_protocol_metadata(original, _declaration())

    result = _apply(tmp_path)

    assert result.success is True
    landed = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert landed == expected_merge
    preserved_fragments = (
        "# project header\n",
        'name = "protocols-dev" # package identity\n',
        "[tool.unrelated]\n",
        "answer = 42 # keep inline\n",
    )
    assert all(fragment in landed for fragment in preserved_fragments)
    assert landed.index("[tool.unrelated]") < landed.index("[tool.axm-init.protocols]")
