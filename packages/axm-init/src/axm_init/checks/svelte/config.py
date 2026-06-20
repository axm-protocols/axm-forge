"""Svelte config gold-standard checks — ``svelte.config.js`` presence.

A SvelteKit project must ship a ``svelte.config.{js,ts}`` (it drives the
compiler, adapters and ``$lib`` aliases). This is the svelte delta over the
shared node manifest checks.
"""

from __future__ import annotations

from pathlib import Path

from axm_init.models.check import CheckResult

__all__ = ["check_svelte_config"]

_SVELTE_CONFIGS = ("svelte.config.js", "svelte.config.ts")


def check_svelte_config(project: Path) -> CheckResult:
    """Check: a ``svelte.config.{js,ts}`` is present at the project root."""
    if any((project / name).is_file() for name in _SVELTE_CONFIGS):
        return CheckResult(
            name="config.svelte_config",
            category="config",
            passed=True,
            weight=3,
            message="svelte.config found",
            details=[],
            fix="",
        )
    return CheckResult(
        name="config.svelte_config",
        category="config",
        passed=False,
        weight=3,
        message="No svelte.config.js",
        details=[],
        fix="Add a svelte.config.js (SvelteKit project config).",
    )
