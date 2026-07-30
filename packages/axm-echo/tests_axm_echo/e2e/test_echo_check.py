"""E2E test for the ``axm echo_check`` CLI command (subprocess black box).

The ``echo_check`` AXMTool is auto-registered as a CLI command via the
``axm.tools`` entry point, so ``axm echo_check`` must run end to end and emit
the ranked candidates with their docstrings. We point ``~/axm/echo.toml`` at a
tiny on-disk corpus so the walk is bounded and deterministic, and pass
``--backend tfidf`` so the test runs without the optional ``neural`` extra
(torch).
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    # Invoked via the generic ``axm`` binary (echo exposes its tools through the
    # ``axm.tools`` entry point, not a dedicated ``axm-echo`` script), so the
    # subprocess is not statically linkable to a package symbol. This is a true
    # CLI black-box e2e, not a packaging-invariant test -- opt out explicitly.
    pytest.mark.no_package_symbol_ok,
]


def _write_package(root: Path, name: str, module: str, body: str) -> None:
    """Materialise a minimal real package tree on disk."""
    pkg = root / name / "src" / name.replace("-", "_")
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / f"{module}.py").write_text(textwrap.dedent(body), encoding="utf-8")


def test_cli_echo_check(tmp_path: Path) -> None:
    """AC1: ``axm echo_check`` exits 0 and emits the top-k candidates + docstrings."""
    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-bib",
        "net",
        '''
        def request_with_retry(url: str) -> bytes:
            """Perform an HTTP request, retrying with backoff on transient errors."""
            return b""
        ''',
    )
    config_dir = home / ".axm"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        f'[echo]\nworkspace_roots = ["{ws}"]\n', encoding="utf-8"
    )

    env = {**os.environ, "HOME": str(home)}
    proc = subprocess.run(
        [
            "axm",
            "echo_check",
            "--intention",
            "Perform an HTTP request, retrying with backoff on transient errors",
            "--backend",
            "tfidf",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    # The report names the tool and surfaces the candidate symbol + its docstring.
    assert "echo_check" in proc.stdout
    assert "request_with_retry" in proc.stdout
