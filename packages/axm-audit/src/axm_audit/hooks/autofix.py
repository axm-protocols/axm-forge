"""Autofix hook — ruff fix + format before gate evaluation."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

from axm_audit.core.runner import run_in_project

__all__ = ["AutofixHook"]

logger = logging.getLogger(__name__)

_RUFF_CONFIG_ERROR = 2
_FIXED_RE = re.compile(r"\((\d+) fixed,")


def _parse_fixed_count(stdout: str) -> int:
    """Extract the number of fixes from ruff check output."""
    match = _FIXED_RE.search(stdout)
    return int(match.group(1)) if match else 0


class AutofixHook:
    """Run ruff fix + format as a pre-gate hook."""

    def execute(self, context: dict[str, Any], **params: Any) -> HookResult:
        """Run ``ruff check --fix .`` then ``ruff format .``.

        Args:
            context: Hook context with ``working_dir``.
            **params: Ignored.

        Returns:
            HookResult with ``fixed`` count in metadata.
        """
        project_path = Path(context.get("working_dir", "."))

        try:
            fix_result = run_in_project(
                ["ruff", "check", "--fix", "."],
                project_path,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return HookResult.ok(skipped=True)

        if fix_result.returncode == _RUFF_CONFIG_ERROR:
            logger.warning("ruff config error: %s", fix_result.stderr[:500])
            return HookResult.ok(fixed=0)

        fixed = _parse_fixed_count(fix_result.stdout)

        try:
            run_in_project(
                ["ruff", "format", "."],
                project_path,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return HookResult.ok(skipped=True)

        return HookResult.ok(fixed=fixed)
