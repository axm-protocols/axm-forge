"""Fresh interpreter qualification of generic-base dead-code analysis."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

_PROBE = """
import json
import sys
from pathlib import Path
import axm_ast.core.callers as callers
from axm_ast.core.analyzer import analyze_package
from axm_ast.core.dead_code import find_dead_code
print(json.dumps({
    'provider': str(Path(callers.__file__).resolve()),
    'dead': sorted(
        item.name for item in find_dead_code(analyze_package(Path(sys.argv[1])))
    )
}))
"""


@pytest.mark.parametrize("base", ["_Base", "_Base[int]"], ids=["plain", "generic"])
def test_fresh_provider_preserves_identical_dead_code_for_generic_base(
    tmp_path: Path, base: str
) -> None:
    """A new provider process uses this checkout, not cached MCP imports."""
    root = tmp_path / "pair"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "base.py").write_text(
        "class _Base[T]:\n    def inherited(self):\n        return 1\n\n"
        "class _Unused:\n    pass\n",
        encoding="utf-8",
    )
    (root / "consumer.py").write_text(
        f"from .base import _Base\nclass Child({base}):\n    pass\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", _PROBE, str(root)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    expected_provider = Path(__file__).parents[2] / "src/axm_ast/core/callers.py"
    assert Path(payload["provider"]) == expected_provider.resolve()
    assert payload["dead"] == ["Child", "_Unused"]
