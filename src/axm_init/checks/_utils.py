"""Shared utilities for audit check modules."""

from __future__ import annotations

import functools
from collections.abc import Callable
from pathlib import Path
from typing import Any

from axm_init.models.check import CheckResult

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def _load_toml(project: Path) -> dict[str, Any] | None:
    """Load pyproject.toml, return None if missing/corrupt."""
    path = project / "pyproject.toml"
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except Exception:
        return None


def requires_toml(
    check_name: str,
    category: str,
    weight: int,
    fix: str,
) -> Callable[
    [Callable[[Path, dict[str, Any]], CheckResult]],
    Callable[[Path], CheckResult],
]:
    """Decorator that loads pyproject.toml and passes data to the check.

    If pyproject.toml is missing or unparsable, returns a failure
    ``CheckResult`` immediately — eliminating the repeated null-guard
    preamble from every check function.

    The decorated function receives ``(project, data)`` instead of just
    ``(project)`` — where ``data`` is the parsed TOML dict.

    Args:
        check_name: Check result name (e.g. ``"pyproject.ruff"``).
        category: Category key (e.g. ``"pyproject"``).
        weight: Points weight for this check.
        fix: Fix message for the "not found" failure.
    """

    def decorator(
        fn: Callable[[Path, dict[str, Any]], CheckResult],
    ) -> Callable[[Path], CheckResult]:
        """Wrap a check function with TOML pre-loading."""

        @functools.wraps(fn)
        def wrapper(project: Path) -> CheckResult:
            """Load TOML then delegate to the wrapped check."""
            data = _load_toml(project)
            if data is None:
                return CheckResult(
                    name=check_name,
                    category=category,
                    passed=False,
                    weight=weight,
                    message="pyproject.toml not found or unparsable",
                    details=[],
                    fix=fix,
                )
            return fn(project, data)

        return wrapper

    return decorator
