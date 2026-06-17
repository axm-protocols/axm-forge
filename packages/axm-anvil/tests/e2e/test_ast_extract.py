from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_cli_extract_to_new_module(tmp_path: Path) -> None:
    """AC1, AC2: the ``axm ast_extract`` CLI extracts a symbol into a new
    module file that is created on disk."""
    src = tmp_path / "src.py"
    src.write_text(
        textwrap.dedent(
            """\
            def Foo() -> int:
                return 42
            """
        )
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "axm.cli",
            "ast_extract",
            "--path",
            str(tmp_path),
            "--from-file",
            "src.py",
            "--to-file",
            "pkg/new.py",
            "--symbols",
            "Foo",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    new_module = tmp_path / "pkg" / "new.py"
    assert new_module.exists()
    assert "Foo" in new_module.read_text()
