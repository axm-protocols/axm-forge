from __future__ import annotations

import ast
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality._shared import analyze_imports

pytestmark = pytest.mark.integration


FIXTURE_CODE = (
    "import os\n"
    "import sys\n"
    "import subprocess\n"
    "from pathlib import Path\n"
    "from unittest.mock import patch\n"
    "from mypkg import public_a, public_b, _private\n"
    "from mypkg.sub import nested\n"
    "from mypkg._internal import private_helper\n"
    "from mypkg.utils._priv import hidden\n"
)


def test_analyze_imports_is_deterministic(tmp_path: Path) -> None:
    tree = ast.parse(FIXTURE_CODE)
    runs = [analyze_imports(tree, {"mypkg"}, None, tmp_path) for _ in range(3)]
    for i in range(1, len(runs)):
        assert runs[i] == runs[0], f"Run {i} produced different output than run 0"


def test_analyze_imports_findings_match_baseline(tmp_path: Path) -> None:
    tree = ast.parse(FIXTURE_CODE)
    public, internal, modules, has_private, io_modules, io_signals = analyze_imports(
        tree, {"mypkg"}, None, tmp_path
    )

    # Behavioral baseline: structural facts that any correct refactor must preserve.
    assert has_private is True, "Private mypkg alias (`_private`) must be flagged"
    assert any(m.startswith("mypkg") for m in modules), (
        "mypkg modules must appear in the per-module list"
    )
    # IO stdlib modules are tracked separately, not in the per-module list.
    assert "subprocess" in io_modules
    assert any("subprocess" in s for s in io_signals)
    # Outputs remain the documented types.
    assert isinstance(io_modules, set)
    assert isinstance(io_signals, list)
