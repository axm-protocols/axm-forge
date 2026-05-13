"""Functional tests for the `axm-init check` CLI command.

TDD RED — tests the full audit command end-to-end.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from axm_init.cli import app


def _run(*args: str) -> tuple[str, str, int]:
    """Run CLI command and capture stdout/stderr/exit_code."""
    out, err = io.StringIO(), io.StringIO()
    exit_code = 0
    try:
        with redirect_stdout(out), redirect_stderr(err):
            app(args)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
    return out.getvalue(), err.getvalue(), exit_code


class TestCheckSelfTest:
    """axm-init itself should score ≥ B."""

    def test_self_audit(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        stdout, _stderr, _code = _run("check", str(project_root), "--json")
        data = json.loads(stdout)
        assert data["score"] >= 75, f"Self-check score too low: {data['score']}"
        assert data["grade"] in ("A", "B")
