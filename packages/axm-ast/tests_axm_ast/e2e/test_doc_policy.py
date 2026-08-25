"""E2E: ``doc_policy`` importable from the installed package surface."""

from __future__ import annotations

import subprocess
import sys


def test_doc_policy_importable_in_fresh_interpreter() -> None:
    """AC5: importing the module succeeds with no side effects, no extra deps."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import axm_ast.doc_policy as m; "
            "print(m.is_documentation_required.__name__)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "is_documentation_required" in result.stdout
