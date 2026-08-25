"""E2E test for the ``axm doc_gate`` CLI command (subprocess black box).

The ``doc_gate`` AXMTool is auto-registered as a CLI command via the
``axm.tools`` entry point, so ``axm doc_gate`` must run end to end. When mkdocs
is installed we exercise the happy path on a tiny docs tree; the degradation
test strips mkdocs from ``PATH`` so the tool must report a clean failure rather
than crash.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    # Invoked via the generic ``axm`` binary (doc_gate exposes itself through
    # the ``axm.tools`` entry point, not a dedicated script), so the subprocess
    # is not statically linkable to a package symbol -- opt out explicitly.
    pytest.mark.no_package_symbol_ok,
]


def _write_docs_tree(root: Path) -> None:
    """Materialise a minimal, valid mkdocs project on disk."""
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "index.md").write_text("# Home\n", encoding="utf-8")
    (root / "mkdocs.yml").write_text(
        "site_name: Mini\nnav:\n  - Home: index.md\n", encoding="utf-8"
    )


def test_doc_gate_on_mini_docs_tree(tmp_path: Path) -> None:
    """AC4: ``axm doc_gate`` runs on a mini docs tree and reports findings."""
    if shutil.which("mkdocs") is None:
        pytest.skip("mkdocs binary not installed")
    _write_docs_tree(tmp_path)

    proc = subprocess.run(  # noqa: S603
        ["axm", "doc_gate", "--path", str(tmp_path)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "doc_gate" in proc.stdout


def test_doc_gate_degrades_when_mkdocs_unavailable(tmp_path: Path) -> None:
    """AC3/AC4: ``axm doc_gate`` degrades cleanly with no mkdocs on PATH."""
    axm_bin = shutil.which("axm")
    if axm_bin is None:
        pytest.skip("axm binary not found on PATH")
    _write_docs_tree(tmp_path)
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    env = {**os.environ, "PATH": str(empty_bin)}

    proc = subprocess.run(  # noqa: S603
        [axm_bin, "doc_gate", "--path", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    combined = (proc.stdout + proc.stderr).lower()
    # Graceful degradation: a normal exit (0 = printed error, 1 = failure code)
    # carrying a clear mkdocs message -- never a crash / uncaught traceback.
    assert proc.returncode in (0, 1), proc.stderr
    assert "traceback" not in combined
    assert "mkdocs" in combined
