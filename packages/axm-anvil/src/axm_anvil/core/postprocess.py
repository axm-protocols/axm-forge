"""Post-processing: run ruff fix + format on moved files."""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["_ruff_fix"]

_SOURCE_SELECT = "I,E402,F401,F811"
_SOURCE_SELECT_NO_F401 = "I,E402,F811"
_TARGET_SELECT = "I,E402,F811"
_TIMEOUT_SEC = 30


def _run_ruff(action_args: list[str], warnings: list[str]) -> None:
    try:
        result = subprocess.run(  # noqa: S603
            ["ruff", *action_args],  # noqa: S607
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
        warnings.append(f"ruff {action_args[0]} exited {result.returncode}: {stderr}")


def _ruff_fix(source: Path, target: Path, *, reexport: bool = False) -> list[str]:
    """Run ``ruff check --fix`` + ``ruff format`` on source and target.

    F401 (unused imports) is applied only to the source so existing target
    imports unrelated to the move are preserved. When ``reexport=True``,
    F401 is skipped on the source so the injected re-export line survives.
    Non-zero exits and missing ruff are captured as warnings — ruff
    failures never fail a move.
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
    return warnings
