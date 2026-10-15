"""What the target interpreter offers pytest, probed rather than assumed.

``audit_test`` runs the *target's* pytest. Its structured result comes from a
plugin the runner ships (:mod:`axm_audit._report_plugin`) and injects with
``-p`` and ``PYTHONPATH``, so the target needs nothing but pytest itself.
Coverage is the only optional capability (``pytest-cov``): this module asks the
target interpreter, once per run, whether pytest and pytest-cov are importable,
so that a missing piece becomes a typed, explicit outcome instead of pytest's
opaque ``unrecognized arguments`` (exit 4).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from axm_audit.core.runner import run_in_project

__all__ = [
    "MIN_PYTEST_VERSION",
    "PLUGIN_DIR",
    "PLUGIN_MODULE",
    "PytestCapabilities",
    "PytestEnvironmentError",
    "probe_pytest",
]

PLUGIN_MODULE: Final = "axm_audit_report_plugin"
"""Name the reporting plugin is loaded under (``-p``)."""

PLUGIN_DIR: Final = Path(__file__).resolve().parent.parent / "_report_plugin"
"""Directory put on the subprocess ``PYTHONPATH``; it holds the plugin only."""

MIN_PYTEST_VERSION: Final = (7, 0)
"""Oldest pytest whose hooks the reporting plugin relies on."""

_PROBE_TIMEOUT = 120
_PROBE_SCRIPT: Final = """
import importlib.util, json, sys
out = {"python": sys.executable}
try:
    import pytest
    out["pytest"] = pytest.__version__
except BaseException as exc:
    out["pytest_error"] = type(exc).__name__ + ": " + str(exc)
try:
    out["pytest_cov"] = importlib.util.find_spec("pytest_cov") is not None
except Exception:
    out["pytest_cov"] = False
print("AXM_PROBE " + json.dumps(out))
"""
_PROBE_PREFIX: Final = "AXM_PROBE "


class PytestEnvironmentError(ValueError):
    """The target interpreter cannot run ``audit_test``'s pytest session.

    ``interpreter`` is the interpreter that was asked (when known) and
    ``missing`` names what it lacks: ``"pytest"``, ``"pytest>=X"`` or
    ``"interpreter"``.
    """

    def __init__(self, message: str, *, interpreter: str, missing: str) -> None:
        super().__init__(message)
        self.interpreter = interpreter
        self.missing = missing


@dataclass(frozen=True, slots=True)
class PytestCapabilities:
    """What the target interpreter was found to provide."""

    interpreter: str
    pytest_version: str
    coverage_available: bool

    @property
    def coverage_unavailable_reason(self) -> str | None:
        """Why coverage cannot be measured here, or ``None`` when it can."""
        if self.coverage_available:
            return None
        return f"pytest-cov is not installed in {self.interpreter}"


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:2])


def _parse_probe(stdout: str) -> dict[str, object] | None:
    for line in reversed(stdout.splitlines()):
        if line.startswith(_PROBE_PREFIX):
            try:
                data = json.loads(line[len(_PROBE_PREFIX) :])
            except json.JSONDecodeError:
                return None
            return data if isinstance(data, dict) else None
    return None


def probe_pytest(
    project_path: Path,
    *,
    with_packages: list[str] | None = None,
) -> PytestCapabilities:
    """Probe the interpreter ``audit_test`` will use for *project_path*.

    The probe goes through :func:`run_in_project`, hence through exactly the
    interpreter selection the test run itself will get (declared session
    runtime, worktree source environment, project ``.venv``, ``uv`` overlay).

    Raises:
        PytestEnvironmentError: the interpreter cannot be run, has no pytest,
            or has a pytest older than :data:`MIN_PYTEST_VERSION`.
    """
    try:
        result = run_in_project(
            ["python", "-c", _PROBE_SCRIPT],
            project_path,
            timeout=_PROBE_TIMEOUT,
            with_packages=with_packages,
            capture_output=True,
            text=True,
        )
    except (OSError, ValueError) as exc:
        raise PytestEnvironmentError(
            f"cannot run the Python interpreter for {project_path}: {exc}",
            interpreter="unknown",
            missing="interpreter",
        ) from exc

    data = _parse_probe(result.stdout or "")
    if data is None:
        tail = (result.stderr or result.stdout or "").strip()[-600:]
        raise PytestEnvironmentError(
            f"cannot probe the Python interpreter for {project_path} "
            f"(exit {result.returncode}): {tail}",
            interpreter="unknown",
            missing="interpreter",
        )

    interpreter = str(data.get("python", "unknown"))
    version = data.get("pytest")
    if not isinstance(version, str):
        raise PytestEnvironmentError(
            f"pytest is not installed in {interpreter} "
            f"({data.get('pytest_error', 'import failed')}); audit_test runs the "
            "target's own pytest and needs it in that interpreter",
            interpreter=interpreter,
            missing="pytest",
        )
    if _version_tuple(version) < MIN_PYTEST_VERSION:
        needed = ".".join(map(str, MIN_PYTEST_VERSION))
        raise PytestEnvironmentError(
            f"pytest {version} in {interpreter} is too old for audit_test's "
            f"reporting hooks; pytest>={needed} is required",
            interpreter=interpreter,
            missing=f"pytest>={needed}",
        )
    return PytestCapabilities(
        interpreter=interpreter,
        pytest_version=version,
        coverage_available=bool(data.get("pytest_cov")),
    )
