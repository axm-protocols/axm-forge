"""Copier adapter for template-based scaffolding."""

from __future__ import annotations

import logging
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Any

from copier import run_copy
from pydantic import BaseModel

from axm_init.models.results import ScaffoldResult

logger = logging.getLogger(__name__)


class CopierConfig(BaseModel):
    """Configuration for Copier execution."""

    template_path: Path
    destination: Path
    data: dict[str, Any]
    defaults: bool = True
    overwrite: bool = False
    trust_template: bool = False

    model_config = {"extra": "forbid"}


class CopierAdapter:
    """Adapter for Copier template operations.

    Wraps Copier's run_copy function with a Pydantic-based interface
    and returns structured ScaffoldResult.
    """

    def copy(self, config: CopierConfig) -> ScaffoldResult:
        """Execute Copier copy operation.

        Redirects stdout/stderr so that post-copy tasks (git init,
        uv sync, pre-commit install) don't pollute the parent process
        stdio — critical when running inside an MCP server.

        Args:
            config: Copier configuration with template path, destination, and data.

        Returns:
            ScaffoldResult with success status and path.
        """
        try:
            # Redirect stdout/stderr to prevent subprocess output from
            # corrupting MCP JSON-RPC stdio transport.
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = StringIO()
            sys.stderr = StringIO()
            # Also suppress subprocess output via devnull fd
            devnull = os.open(os.devnull, os.O_WRONLY)
            old_fd_out = os.dup(1)
            old_fd_err = os.dup(2)
            os.dup2(devnull, 1)
            os.dup2(devnull, 2)
            if config.trust_template:
                logger.warning(
                    "Running Copier with unsafe=True — template may execute "
                    "arbitrary post-copy tasks."
                )
            try:
                run_copy(
                    src_path=str(config.template_path),
                    dst_path=config.destination,
                    data=config.data,
                    defaults=config.defaults,
                    overwrite=config.overwrite,
                    unsafe=config.trust_template,
                )
            finally:
                # Restore original stdout/stderr
                os.dup2(old_fd_out, 1)
                os.dup2(old_fd_err, 2)
                os.close(old_fd_out)
                os.close(old_fd_err)
                os.close(devnull)
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            # Walk destination to collect all created files (AC1: return file list)
            created: list[str] = sorted(
                str(p.relative_to(config.destination))
                for p in config.destination.rglob("*")
                if p.is_file()
            )
            return ScaffoldResult(
                success=True,
                path=str(config.destination),
                message="Project scaffolded via Copier",
                files_created=created,
            )
        except Exception as e:
            return ScaffoldResult(
                success=False,
                path=str(config.destination),
                message=f"Copier failed: {e}",
            )
