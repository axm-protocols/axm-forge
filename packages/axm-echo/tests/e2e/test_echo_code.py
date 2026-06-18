"""E2E test for the ``axm echo_code`` CLI command (subprocess black box).

The ``echo_code`` AXMTool is auto-registered as a CLI command via the
``axm.tools`` entry point, so ``axm echo_code`` must run end to end and emit
the clusters report. We point ``~/.axm/echo.toml`` at a tiny on-disk corpus so
the walk is bounded and deterministic, and pass ``--backend tfidf`` so the test
runs without the optional ``neural`` extra (torch).
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _write_package(root: Path, name: str, module: str, body: str) -> None:
    """Materialise a minimal real package tree on disk."""
    pkg = root / name / "src" / name.replace("-", "_")
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / f"{module}.py").write_text(textwrap.dedent(body), encoding="utf-8")


def test_cli_echo_code(tmp_path: Path) -> None:
    """AC1: ``axm echo_code`` exits 0 and emits the clusters report."""
    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-a",
        "errors",
        '''
        class RateLimitError(Exception):
            """Raised when the upstream API rate limit has been exceeded."""
        ''',
    )
    _write_package(
        ws,
        "axm-b",
        "errors",
        '''
        class RateLimitError(Exception):
            """Raised when the upstream API rate limit has been exceeded."""
        ''',
    )
    config_dir = home / ".axm"
    config_dir.mkdir()
    (config_dir / "echo.toml").write_text(
        f'workspace_roots = ["{ws}"]\n', encoding="utf-8"
    )

    env = {**os.environ, "HOME": str(home)}
    proc = subprocess.run(
        ["axm", "echo_code", "--backend", "tfidf"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    # The text report names the echo_code tool and reports its cluster count.
    assert "echo_code" in proc.stdout
    assert "cluster" in proc.stdout.lower()
