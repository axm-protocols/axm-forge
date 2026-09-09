from __future__ import annotations

import _thread
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from tomlkit import dumps, parse, table
from tomlkit.items import Table

from axm_init.core.framework import Framework
from axm_init.core.protocol_planner import (
    PlanOperation,
    PlanStatus,
    ProtocolScaffoldPlan,
    plan_protocol_scaffold,
)
from axm_init.models.protocol_scaffold import ProtocolScaffoldDecl
from axm_init.models.results import ScaffoldResult

__all__ = [
    "ProtocolScaffoldRequest",
    "build_protocol_scaffold_result",
    "prepare_protocol_request",
    "preview_protocol_scaffold",
    "register_protocol_profile",
]


type ProtocolPayload = dict[str, object]


@dataclass(frozen=True, slots=True)
class ProtocolScaffoldRequest:
    """Hold one validated protocol-profile request."""

    profile: str
    domain: str
    unit: str | None
    protocols: tuple[ProtocolScaffoldDecl, ...]
    preview: bool


def _payloads(value: list[ProtocolPayload] | str | None) -> list[ProtocolPayload]:
    if value is None:
        return []
    raw: object = json.loads(value) if isinstance(value, str) else value
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        msg = "protocols must be a JSON list of protocol declarations"
        raise ValueError(msg)
    return [{str(key): item for key, item in entry.items()} for entry in raw]


def _validate_options(
    profile: str | None,
    domain: str | None,
    framework: Framework,
) -> tuple[str, str]:
    if profile is None:
        raise ValueError("profile is required for a protocol package")
    if profile != "protocols":
        raise ValueError(f"Unknown profile {profile!r}; expected 'protocols'")
    if framework is not Framework.PYTHON:
        raise ValueError("the protocols profile is available only for Python projects")
    if not domain:
        raise ValueError("domain is required for the protocols profile")
    return profile, domain


def _validate_payloads(
    payloads: list[ProtocolPayload],
    *,
    preview: bool,
    unit: str | None,
) -> None:
    if (preview or unit is not None) and not payloads:
        raise ValueError("protocols must contain at least one declaration")
    if payloads and unit is None:
        raise ValueError("unit is required when protocols are declared")


def _validate_declarations(
    declarations: tuple[ProtocolScaffoldDecl, ...],
    *,
    domain: str,
    unit: str | None,
) -> None:
    if any(declaration.domain != domain for declaration in declarations):
        raise ValueError("protocol domain must match the requested domain")
    if unit is not None and any(
        declaration.unit != unit for declaration in declarations
    ):
        raise ValueError("protocol unit must match the requested unit")


def prepare_protocol_request(  # noqa: PLR0913
    *,
    profile: str | None,
    domain: str | None,
    unit: str | None,
    protocols: list[ProtocolPayload] | str | None,
    preview: bool,
    framework: Framework,
) -> ProtocolScaffoldRequest | str | None:
    """Validate protocol options before any target filesystem mutation."""
    requested = any((profile, domain, unit, protocols is not None, preview))
    if not requested:
        return None
    try:
        valid_profile, valid_domain = _validate_options(profile, domain, framework)
        payloads = _payloads(protocols)
        _validate_payloads(payloads, preview=preview, unit=unit)
        declarations = tuple(
            ProtocolScaffoldDecl.model_validate(
                {**payload, "domain": valid_domain, "unit": unit}
            )
            for payload in payloads
        )
        _validate_declarations(
            declarations,
            domain=valid_domain,
            unit=unit,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return str(exc)
    return ProtocolScaffoldRequest(
        profile=valid_profile,
        domain=valid_domain,
        unit=unit,
        protocols=declarations,
        preview=preview,
    )


def build_protocol_scaffold_result(  # noqa: PLR0913
    plan: ProtocolScaffoldPlan,
    *,
    profile: str,
    mode: str,
    root: PurePosixPath,
    graph_names: tuple[str, ...],
    preview: bool,
) -> ScaffoldResult:
    """Project a typed planner result into the shared structured result."""
    grouped: dict[PlanStatus, list[str]] = {status: [] for status in PlanStatus}
    for operation in plan.operations:
        grouped[operation.status].append(operation.path.as_posix())
    return ScaffoldResult(
        success=True,
        path=root.as_posix(),
        message="Protocol scaffold preview",
        profile=profile,
        mode=mode,
        root=root.as_posix(),
        preview=preview,
        created=grouped[PlanStatus.CREATE],
        updated=grouped[PlanStatus.UPDATE],
        unchanged=grouped[PlanStatus.UNCHANGED],
        conflicts=grouped[PlanStatus.CONFLICT],
        protocols=list(graph_names),
    )


def _inventory(root: Path) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            inventory[path.relative_to(root).as_posix()] = path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            continue
    return inventory


def _combine_operations(
    current: dict[PurePosixPath, PlanOperation],
    operations: tuple[PlanOperation, ...],
) -> None:
    for operation in operations:
        previous = current.get(operation.path)
        if previous is None or previous.status is PlanStatus.UNCHANGED:
            current[operation.path] = operation


def _planned_destination(root: Path, operation: PlanOperation) -> Path:
    """Resolve one planned path and reject every escape from the target root."""
    if operation.path.is_absolute():
        raise ValueError(f"outside-root: {operation.path}")
    root_resolved = root.resolve()
    lexical = root
    for part in operation.path.parts:
        lexical /= part
        if lexical.is_symlink():
            link_target = lexical.resolve()
            try:
                link_target.relative_to(root_resolved)
            except ValueError as exc:
                raise ValueError(f"outward-symlink: {operation.path}") from exc
    destination = (root / operation.path.as_posix()).resolve()
    try:
        destination.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"outside-root: {operation.path}") from exc
    return destination


def _occupancy_incompatible(operation: PlanOperation, destination: Path) -> bool:
    """Report whether an operation's status contradicts its destination state."""
    occupied = destination.exists() or destination.is_symlink()
    if operation.status is PlanStatus.CONFLICT:
        return True
    if operation.status is PlanStatus.CREATE:
        return occupied
    if operation.status in {PlanStatus.UPDATE, PlanStatus.UNCHANGED}:
        return not occupied or not destination.is_file()
    return False


def _content_incompatible(operation: PlanOperation) -> bool:
    """Report whether a mutating operation is missing its content payload."""
    return (
        operation.status in {PlanStatus.CREATE, PlanStatus.UPDATE}
        and operation.content is None
    )


def _preflight_protocol_plan(
    root: Path,
    plan: ProtocolScaffoldPlan,
) -> tuple[tuple[PlanOperation, Path], ...]:
    """Validate the complete plan before allowing its first mutation."""
    resolved: list[tuple[PlanOperation, Path]] = []
    for operation in plan.operations:
        destination = _planned_destination(root, operation)
        if _occupancy_incompatible(operation, destination) or _content_incompatible(
            operation
        ):
            raise ValueError(f"occupied-incompatible: {operation.path}")
        resolved.append((operation, destination))
    return tuple(resolved)


def _missing_parent_directories(root: Path, destination: Path) -> list[Path]:
    """Return missing parents in creation order, bounded by root."""
    missing: list[Path] = []
    parent = destination.parent
    while parent != root and not parent.exists():
        missing.append(parent)
        parent = parent.parent
    missing.reverse()
    return missing


def _rollback_protocol_application(
    *,
    created_files: list[Path],
    created_directories: list[Path],
    original_files: dict[Path, bytes],
    metadata_path: Path,
    original_metadata: bytes,
) -> None:
    """Restore the exact pre-application bytes and remove owned creations."""
    for path in reversed(created_files):
        if path.is_file() or path.is_symlink():
            path.unlink()
    for path, content in original_files.items():
        path.write_bytes(content)
    metadata_path.write_bytes(original_metadata)
    for path in reversed(created_directories):
        if path.is_dir():
            path.rmdir()


def _apply_protocol_plan(
    root: Path,
    plan: ProtocolScaffoldPlan,
    resolved: tuple[tuple[PlanOperation, Path], ...],
) -> None:
    """Apply a preflighted plan with in-memory application-level rollback."""
    metadata_path = root / "pyproject.toml"
    original_metadata = metadata_path.read_bytes()
    original_files = {
        destination: destination.read_bytes()
        for operation, destination in resolved
        if operation.status is PlanStatus.UPDATE
    }
    created_files: list[Path] = []
    created_directories: list[Path] = []
    try:
        for operation, destination in resolved:
            if operation.status not in {PlanStatus.CREATE, PlanStatus.UPDATE}:
                continue
            for directory in _missing_parent_directories(root, destination):
                directory.mkdir()
                created_directories.append(directory)
            if operation.status is PlanStatus.CREATE:
                created_files.append(destination)
            content = operation.content
            if content is None:
                raise ValueError(f"occupied-incompatible: {operation.path}")
            destination.write_text(content, encoding="utf-8")
        metadata = plan.metadata.encode()
        if metadata != original_metadata:
            metadata_path.write_text(plan.metadata, encoding="utf-8")
    except Exception:
        _rollback_protocol_application(
            created_files=created_files,
            created_directories=created_directories,
            original_files=original_files,
            metadata_path=metadata_path,
            original_metadata=original_metadata,
        )
        raise


@dataclass
class _RootLockEntry:
    lock: _thread.RLock
    users: int = 0


_ROOT_LOCKS: dict[Path, _RootLockEntry] = {}
_ROOT_LOCKS_GUARD = threading.Lock()


@contextmanager
def _target_root_lock(root: Path) -> Iterator[None]:
    canonical_root = root.resolve()
    with _ROOT_LOCKS_GUARD:
        entry = _ROOT_LOCKS.get(canonical_root)
        if entry is None:
            entry = _RootLockEntry(lock=_thread.RLock())
            _ROOT_LOCKS[canonical_root] = entry
        entry.users += 1
    entry.lock.acquire()
    try:
        yield
    finally:
        entry.lock.release()
        with _ROOT_LOCKS_GUARD:
            entry.users -= 1
            if entry.users == 0:
                _ROOT_LOCKS.pop(canonical_root, None)


def preview_protocol_scaffold(
    root: Path,
    request: ProtocolScaffoldRequest,
) -> ScaffoldResult:
    """Plan declarations and serialize applications by canonical target root."""
    if request.preview:
        return _preview_protocol_scaffold_unlocked(root, request)
    canonical_root = root.resolve()
    with _target_root_lock(canonical_root):
        return _preview_protocol_scaffold_unlocked(canonical_root, request)


def _preview_protocol_scaffold_unlocked(
    root: Path,
    request: ProtocolScaffoldRequest,
) -> ScaffoldResult:
    """Plan all declarations against a virtual inventory without writing."""
    metadata_path = root / "pyproject.toml"
    metadata = metadata_path.read_text(encoding="utf-8")
    inventory = _inventory(root)
    combined: dict[PurePosixPath, PlanOperation] = {}
    for declaration in request.protocols:
        plan = plan_protocol_scaffold(declaration, metadata, inventory)
        _combine_operations(combined, plan.operations)
        metadata = plan.metadata
        for operation in plan.operations:
            if operation.content is not None:
                inventory[operation.path.as_posix()] = operation.content
    final_plan = ProtocolScaffoldPlan(
        operations=tuple(combined[path] for path in sorted(combined)),
        metadata=metadata,
    )
    if not request.preview:
        resolved = _preflight_protocol_plan(root, final_plan)
        _apply_protocol_plan(root, final_plan, resolved)
    return build_protocol_scaffold_result(
        final_plan,
        profile=request.profile,
        mode="unit",
        root=PurePosixPath(str(root)),
        graph_names=tuple(item.graph_name for item in request.protocols),
        preview=request.preview,
    )


def register_protocol_profile(root: Path, domain: str) -> None:
    """Persist the profile while serialized with applications on this root."""
    canonical_root = root.resolve()
    with _target_root_lock(canonical_root):
        _register_protocol_profile_unlocked(canonical_root, domain)


def _register_protocol_profile_unlocked(root: Path, domain: str) -> None:
    """Persist the package-level protocol profile in its project metadata."""
    metadata_path = root / "pyproject.toml"
    document = parse(metadata_path.read_text(encoding="utf-8"))
    tool = document.get("tool")
    if not isinstance(tool, Table):
        tool = table()
        document["tool"] = tool
    axm_init = tool.get("axm-init")
    if not isinstance(axm_init, Table):
        axm_init = table()
        tool["axm-init"] = axm_init
    profile = axm_init.get("protocols")
    if not isinstance(profile, Table):
        profile = table()
        axm_init["protocols"] = profile
    profile["schema_version"] = 1
    profile["domain"] = domain
    metadata_path.write_text(dumps(document), encoding="utf-8")
