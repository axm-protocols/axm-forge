from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule

__all__: list[str] = []


_AXM_AST_REPO = (
    Path(__file__).resolve().parents[2] / ".." / ".." / "axm-ast"
).resolve()
_PROTOTYPE = (
    Path(__file__).resolve().parents[2] / "scripts" / "detect_private_imports.py"
).resolve()


@pytest.mark.integration
def test_axm_ast_byte_parity_with_prototype() -> None:
    if not _AXM_AST_REPO.exists():
        pytest.skip(f"axm-ast repo not available at {_AXM_AST_REPO}")
    if not _PROTOTYPE.exists():
        pytest.skip(f"prototype script not available at {_PROTOTYPE}")

    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(_PROTOTYPE), "--all", "--json"],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(_AXM_AST_REPO),
    )
    proto_data = json.loads(proc.stdout)
    expected = {
        (Path(item["test_file"]).name, item["private_symbol"], item["symbol_kind"])
        for item in proto_data
    }

    result = PrivateImportsRule().check(_AXM_AST_REPO)
    findings = result.details["findings"]  # type: ignore[index]
    actual = {
        (Path(f["test_file"]).name, f["private_symbol"], f["symbol_kind"])
        for f in findings
    }
    assert actual == expected
