"""Integration: real ruff diagnostics flow through the removal filter."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from axm_edit.services.lint_diff import (
    extract_import_removals,
    extract_rules_by_file,
)

_RUFF = os.path.join(os.path.dirname(sys.executable), "ruff")


@pytest.mark.integration
@pytest.mark.skipif(not os.path.exists(_RUFF), reason="ruff binary not in venv")
def test_real_ruff_f401_removal_flows_through_filter(tmp_path: Path) -> None:
    src = tmp_path / "sample.py"
    src.write_text("import os\n\nx = 1\n")

    proc = subprocess.run(
        [_RUFF, "check", "--select", "F401", "--output-format", "concise", str(src)],
        capture_output=True,
        text=True,
        check=False,
    )
    diagnostics = proc.stdout.splitlines()

    # extract_rules_by_file (reused authority) classifies the F401 for the file...
    rules = extract_rules_by_file(diagnostics)
    assert any("F401" in codes for codes in rules.values())

    # ...and the filter surfaces it as a named removal.
    removals = extract_import_removals(diagnostics)
    surfaced = [r for entries in removals.values() for r in entries]
    assert any(r.code == "F401" and r.name == "os" for r in surfaced)
