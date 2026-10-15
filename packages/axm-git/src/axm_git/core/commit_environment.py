"""Invocation-local transport for a declared commit dependency environment."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from types import MappingProxyType
from typing import TypedDict

from axm.tools.dependency_reads import DependencyEnvironment

__all__: list[str] = []

_ENVIRONMENT: ContextVar[Mapping[str, str] | None] = ContextVar(
    "axm_git_commit_environment", default=None
)
_RUNTIME_KEYS = (
    "PATH",
    "PYTHONPATH",
    "PYTHONDONTWRITEBYTECODE",
    "AXM_DEPENDENCY_INTERPRETER",
    "AXM_DEPENDENCY_PACKAGE_ROOT",
)


class _EnvironmentOptions(TypedDict, total=False):
    """Only the optional subprocess environment keyword."""

    env: Mapping[str, str]


@contextmanager
def commit_environment(environment: Mapping[str, str] | None) -> Iterator[None]:
    """Bind an immutable snapshot for this invocation and always restore it."""
    snapshot = None if environment is None else MappingProxyType(dict(environment))
    token = _ENVIRONMENT.set(snapshot)
    try:
        yield
    finally:
        _ENVIRONMENT.reset(token)


def environment_options(
    explicit: Mapping[str, str] | None = None,
) -> _EnvironmentOptions:
    """Snapshot scoped runtime plus local Git options for one subprocess.

    Without a scope, an explicit mapping is a complete subprocess environment.
    Within a scope, explicit options overlay it while declared Python runtime
    keys remain authoritative. No mapping supplied by a caller is mutated.
    """
    scoped = _ENVIRONMENT.get()
    if scoped is None:
        return {} if explicit is None else {"env": dict(explicit)}
    merged = dict(scoped)
    if explicit is not None:
        merged.update(explicit)
        merged.update({key: scoped[key] for key in _RUNTIME_KEYS if key in scoped})
    return {"env": merged}


def dependency_environment(
    candidate: Path,
    declared: Mapping[str, object] | DependencyEnvironment | None,
) -> Mapping[str, str] | None:
    """Validate the explicit read runtime before staging, without preparing it."""
    if declared is None:
        return None
    if isinstance(declared, DependencyEnvironment):
        declared = declared.to_mapping()
    if not isinstance(declared, Mapping):
        raise ValueError("dependency_environment must be a mapping")
    environment = DependencyEnvironment.from_mapping(declared)
    _check_locations(candidate, environment)
    result = dict(os.environ)
    result["PATH"] = (
        str(Path(environment.interpreter).parent) + os.pathsep + result.get("PATH", "")
    )
    result["PYTHONPATH"] = os.pathsep.join(_candidate_sources(candidate, environment))
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    result["AXM_DEPENDENCY_INTERPRETER"] = environment.interpreter
    result["AXM_DEPENDENCY_PACKAGE_ROOT"] = environment.package_root
    return MappingProxyType(result)


def _check_locations(candidate: Path, environment: DependencyEnvironment) -> None:
    """Require an existing lexical interpreter and a candidate-owned package."""
    interpreter = Path(environment.interpreter)
    package = Path(environment.package_root)
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise ValueError("dependency interpreter must be an executable file")
    if not package.is_dir() or not package.is_relative_to(candidate.resolve()):
        raise ValueError("dependency package_root must belong to the candidate")


def _candidate_sources(
    candidate: Path, environment: DependencyEnvironment
) -> list[str]:
    """Put the candidate package and sibling sources before declared dependencies."""
    package = Path(environment.package_root)
    paths = [
        str(package / "src"),
        str(package),
        *(str(path) for path in sorted(candidate.glob("packages/*/src"))),
        *environment.pythonpath,
    ]
    return list(dict.fromkeys(paths))
