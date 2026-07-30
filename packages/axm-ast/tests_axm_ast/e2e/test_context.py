"""E2E tests for the ``axm-ast context`` CLI command.

Subprocess black box. The ``context`` command detects a uv workspace and,
when one is found, dumps the workspace context. The AXM-1889 refactor
factors the detect-then-redetect pattern into a shared helper; the
observable CLI output must remain identical.
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
    """Create a 2-package uv workspace."""
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
        {"util.py": "VALUE = 1\n"},
    )
    _write_pkg(
        root,
        "packages/pkg_a",
        "pkg-a",
        "pkg_a",
        {
            "core.py": "X = 1\n",
            "cli.py": "from pkg_a import core\nfrom pkg_b import util\n",
        },
    )
    return root


def test_context_workspace_output_unchanged(mini_workspace: Path) -> None:
    """AC2: ``context`` on a workspace detects it once and dumps the workspace
    context; output and exit code are unchanged by the helper refactor."""
    proc = subprocess.run(
        [
            "axm-ast",
            "context",
            str(mini_workspace),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)
    # A workspace context carries both members; only reachable if the
    # workspace branch was actually taken (single detection at boundary).
    blob = json.dumps(payload)
    assert "pkg_a" in blob and "pkg_b" in blob, blob
