"""E2E: the ``ast_doc_impact`` tool suppresses doc false positives.

Subprocess black box. Drives the registered ``DocImpactTool`` in a fresh
interpreter over a fixture mixing docstringed, private and gap symbols, and
asserts the JSON ``undocumented`` list contains only the genuine public
docstring-less gap.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

_SRC = (
    '"""Module."""\n'
    "\n"
    "\n"
    "def _helper() -> int:\n"
    '    """Docstringed private helper."""\n'
    "    return 1\n"
    "\n"
    "\n"
    "class AlreadyDocumented:\n"
    '    """Already-documented class."""\n'
    "\n"
    "\n"
    "def check_thing() -> bool:\n"
    '    """Docstringed check function."""\n'
    "    return True\n"
    "\n"
    "\n"
    "def _untouched() -> int:\n"
    "    return 2\n"
    "\n"
    "\n"
    "def real_gap() -> int:\n"
    "    return 3\n"
)

_SYMBOLS = ["_helper", "AlreadyDocumented", "check_thing", "_untouched", "real_gap"]


@pytest.fixture
def mixed_pkg(tmp_path: Path) -> Path:
    """Create a src-layout package mixing docstringed / private / gap symbols."""
    pkg = tmp_path / "src" / "probe"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""probe."""\n')
    (pkg / "core.py").write_text(_SRC)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "probe"\nversion = "0.1.0"\n'
    )
    return tmp_path


def test_doc_impact_reports_only_real_gap(mixed_pkg: Path) -> None:
    """doc_impact keeps the real public gap and drops every false positive."""
    # Inline black-box driver: fresh interpreter → the real tool → JSON on stdout.
    driver = (
        "import json, sys\n"
        "from axm_ast.tools.doc_impact import DocImpactTool\n"
        "res = DocImpactTool().execute("
        "path=sys.argv[1], symbols=json.loads(sys.argv[2]))\n"
        "assert res.success, res.error\n"
        "print(json.dumps(res.data['undocumented']))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", driver, str(mixed_pkg), json.dumps(_SYMBOLS)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    undocumented = json.loads(proc.stdout.strip().splitlines()[-1])

    # Only the genuine public docstring-less symbol survives.
    assert undocumented == ["real_gap"]
