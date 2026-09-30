"""Readiness uses the validation runners and their command builders."""

from __future__ import annotations

import tempfile
from pathlib import Path

from axm_audit.core.rules.quality_rules import (
    build_quality_commands,
    detect_env_incompleteness,
)
from axm_audit.core.runner import run_in_project
from axm_audit.core.test_runner import build_pytest_cmd, run_pytest

__all__ = ["validation_readiness"]


def validation_readiness(project_path: Path) -> dict[str, str]:
    """Return instrument failures; ordinary lint/type findings are runnable."""
    failures: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="axm_readiness_") as tmp:
        commands = {
            "pytest": build_pytest_cmd(
                report_path=Path(tmp) / "collection.json",
                coverage_path=None,
                files=None,
                markers=None,
                stop_on_first=False,
                collect_only=True,
            ),
        }
        commands.update(build_quality_commands(project_path))
        for instrument, command in commands.items():
            try:
                if instrument == "pytest":
                    result = run_pytest(command, project_path)
                else:
                    result = run_in_project(
                        command,
                        project_path,
                        with_packages=["ruff"] if instrument == "ruff" else None,
                        capture_output=True,
                        text=True,
                    )
            except (OSError, ValueError) as exc:
                failures[instrument] = str(exc)
                continue
            failed = result.returncode not in (0, 1)
            if instrument == "pytest":
                failed = result.returncode != 0
            elif instrument == "mypy":
                failed |= (
                    detect_env_incompleteness(result.stdout or "", result.returncode)
                    is not None
                )
            if failed:
                failures[instrument] = (
                    f"exit code {result.returncode}\n"
                    f"{result.stdout or ''}{result.stderr or ''}"
                ).strip()
    return failures
