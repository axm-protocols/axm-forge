"""E2E tests for the ``axm-ast callers`` CLI command.

Subprocess black box. The ``callers`` command detects a uv workspace and,
when one is found, searches call-sites across all workspace members. The
AXM-1889 refactor factors the detect-then-redetect pattern into a shared
helper; the observable CLI output must remain identical.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _write_pkg(
    root: Path,
    pkg_dir: str,
    dist_name: str,
    import_name: str,
    files: dict[str, str],
) -> None:
    """Scaffold a workspace member package under ``root/pkg_dir``."""
    pkg_root = root / pkg_dir
    src = pkg_root / "src" / import_name
    src.mkdir(parents=True, exist_ok=True)
    (pkg_root / "pyproject.toml").write_text(
        f'[project]\nname = "{dist_name}"\nversion = "0.1.0"\n'
        'requires-python = ">=3.12"\n'
    )
    (src / "__init__.py").write_text("")
    for rel, content in files.items():
        (src / rel).write_text(content)


@pytest.fixture
def mini_workspace(tmp_path: Path) -> Path:
    """Create a 2-package uv workspace where pkg_a calls a pkg_b helper."""
    root = tmp_path / "ws"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    (root / "packages").mkdir()
    _write_pkg(
        root,
        "packages/pkg_b",
        "pkg-b",
        "pkg_b",
        {"util.py": "def helper():\n    return 1\n"},
    )
    _write_pkg(
        root,
        "packages/pkg_a",
        "pkg-a",
        "pkg_a",
        {
            "core.py": (
                "from pkg_b.util import helper\n\ndef run():\n    return helper()\n"
            ),
        },
    )
    return root


def test_callers_workspace_output_unchanged(mini_workspace: Path) -> None:
    """AC2: ``callers`` on a workspace detects it once and finds cross-package
    callers; output and exit code are unchanged by the helper refactor."""
    proc = subprocess.run(
        [
            "axm-ast",
            "callers",
            str(mini_workspace),
            "--symbol",
            "helper",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    results = json.loads(proc.stdout)
    assert isinstance(results, list)
    # The cross-package call-site in pkg_a.core.run must be discovered,
    # which is only possible if the workspace was actually analyzed.
    modules = {r["module"] for r in results}
    assert any("core" in m for m in modules), results
