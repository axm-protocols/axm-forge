"""Post-processing: run ruff fix + format on moved files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import libcst as cst

__all__ = ["_ruff_fix"]

_SOURCE_SELECT = "I,E402,F401,F811"
_SOURCE_SELECT_NO_F401 = "I,E402,F811"
_TARGET_SELECT = "I,E402,F811"
_TIMEOUT_SEC = 30
_RUFF_MISSING_MARKERS = ("no module named ruff", "modulenotfounderror")


def _ruff_unavailable(stderr: str) -> bool:
    """True when ``python -m ruff`` reported that the ruff module is absent."""
    low = stderr.lower()
    return any(marker in low for marker in _RUFF_MISSING_MARKERS)


def _run_ruff(action_args: list[str], warnings: list[str]) -> None:
    """Run one ruff action via ``sys.executable -m ruff``, collecting warnings.

    Uses the interpreter's own ruff (not an ambient ``PATH`` binary). A missing
    ruff module yields a distinct "unavailable — skipped" warning; any other
    non-zero exit or launch failure is captured as a warning. Never raises.
    """
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "ruff", *action_args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        warnings.append(f"ruff {action_args[0]} failed to launch: {exc}")
        return
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if _ruff_unavailable(stderr):
            warnings.append(
                "ruff unavailable — post-move cleanup skipped "
                "(install ruff in the runtime environment to enable it)"
            )
            return
        warnings.append(f"ruff {action_args[0]} exited {result.returncode}: {stderr}")


def _ruff_fix(source: Path, target: Path, *, reexport: bool = False) -> list[str]:
    """Run ``ruff check --fix`` + ``ruff format`` on source and target.

    F401 (unused imports) is applied only to the source so existing target
    imports unrelated to the move are preserved. When ``reexport=True``,
    F401 is skipped on the source so the injected re-export line survives.
    Non-zero exits and missing ruff are captured as warnings — ruff
    failures never fail a move.

    Ruff is invoked through ``sys.executable -m ruff`` so the interpreter's
    own ruff is used rather than an ambient ``PATH`` binary. Ruff is declared
    only as a dev dependency by design: post-move cleanup is best-effort, so
    a runtime-only install that lacks ruff is not an error. That case is
    surfaced explicitly as a ``ruff unavailable — post-move cleanup skipped``
    warning (never a silent no-op, never a failed move).
    """
    warnings: list[str] = []
    source_s, target_s = str(source), str(target)
    source_select = _SOURCE_SELECT_NO_F401 if reexport else _SOURCE_SELECT
    _run_ruff(
        ["check", "--select", source_select, "--fix", "--quiet", source_s], warnings
    )
    _run_ruff(
        ["check", "--select", _TARGET_SELECT, "--fix", "--quiet", target_s], warnings
    )
    _run_ruff(["format", "--quiet", source_s, target_s], warnings)
    _revalidate(source, warnings)
    _revalidate(target, warnings)
    return warnings


def _revalidate(path: Path, warnings: list[str]) -> None:
    """Re-parse ``path`` after the ruff pass; warn if it no longer parses.

    A destructive ``ruff --fix`` could mutate an already-validated file into
    invalid syntax. Re-parsing with ``cst.parse_module`` catches that and
    surfaces it through ``warnings`` so it cannot land silently. Parse
    failures are reported, never raised — ruff failures never fail a move.
    """
    try:
        cst.parse_module(path.read_text())
    except (cst.ParserSyntaxError, OSError, UnicodeDecodeError) as exc:
        warnings.append(f"post-ruff re-validation failed for {path}: {exc}")
