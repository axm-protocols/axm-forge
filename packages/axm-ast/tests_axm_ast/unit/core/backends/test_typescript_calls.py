"""Unit tests for TypeScript call-site extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_typescript")

from axm_ast.core.backends.typescript import TypeScriptBackend
from axm_ast.models.calls import CallSite
from axm_ast.models.nodes import ModuleInfo

_SRC = """\
import { helper } from "./util.js";

export function run(): number {
  const a = helper(3);
  return obj.method(a);
}
"""


def _calls(tmp_path: Path) -> list[CallSite]:
    """Write the sample and extract its call-sites via the TS backend."""
    src = tmp_path / "main.ts"
    src.write_text(_SRC)
    module = ModuleInfo(path=src)
    return TypeScriptBackend().extract_calls(module)


def test_direct_call_extracted(tmp_path: Path) -> None:
    """A direct ``helper(3)`` call is captured with full confidence."""
    calls = _calls(tmp_path)
    helper = next(c for c in calls if c.symbol == "helper")
    assert helper.confidence == 1.0
    assert helper.call_expression == "helper(3)"


def test_call_context_is_enclosing_function(tmp_path: Path) -> None:
    """The call's context is the enclosing function name."""
    calls = _calls(tmp_path)
    helper = next(c for c in calls if c.symbol == "helper")
    assert helper.context == "run"


def test_member_call_lower_confidence(tmp_path: Path) -> None:
    """A ``obj.method()`` member call is captured by property name, conf 0.5."""
    calls = _calls(tmp_path)
    method = next(c for c in calls if c.symbol == "method")
    assert method.confidence == 0.5


def test_module_name_defaults_to_stem(tmp_path: Path) -> None:
    """CallSite.module defaults to the file stem."""
    calls = _calls(tmp_path)
    assert all(c.module == "main" for c in calls)
