"""Integration: abstract-method following via ast_context / ast_inspect.

Exercises the ``ToolAstContext`` (``ast_context``) / ``ast_inspect`` path that
resolves an ABC's ``@abstractmethod`` to its concrete subclass override, against
a real on-disk fixture parsed by tree-sitter (no mocks/stubs).

Regression net for the L4 finding: ``ast_inspect`` reports a hardcoded
``function`` kind and never surfaces abstractness, and the abstract -> concrete
following path was entirely untested. Neutralising the following logic (so it
returns the abstract declaration, or nothing) must fail these tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest

from axm_ast.tools.context import ContextTool
from axm_ast.tools.inspect import InspectTool

pytestmark = pytest.mark.integration

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "abstract_following.py"

# L4 06a5ca28-fb63 regression: ``ast_inspect`` must surface the parser-derived
# FunctionKind through ``axm_ast.tools.inspect_detail.function_detail`` -- an
# ``@abstractmethod`` reports ``abstract`` (previously a hardcoded ``function``).
_KIND_L4_PIN = (
    "L4 06a5ca28-fb63: ast_inspect must surface the parser-derived kind; an "
    "@abstractmethod reports 'abstract', not the old hardcoded 'function'."
)


class _Fixture(NamedTuple):
    """Isolated on-disk copy of the abstract-following fixture."""

    pkg: str
    abstract_line: int
    concrete_line: int


def _method_def_line(source: str, class_name: str, method: str) -> int:
    """Return the 1-based line of ``def {method}`` inside ``class {class_name}``."""
    in_class = False
    for lineno, raw in enumerate(source.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith(f"class {class_name}"):
            in_class = True
            continue
        if in_class and stripped.startswith("class "):
            break
        if in_class and stripped.startswith(f"def {method}("):
            return lineno
    raise AssertionError(f"def {method} not found in class {class_name}")


@pytest.fixture
def abstract_pkg(tmp_path: Path) -> _Fixture:
    """Copy the real fixture into an isolated package parsed by tree-sitter."""
    source = _FIXTURE.read_text(encoding="utf-8")
    pkg_dir = tmp_path / "abstract_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "abstract_following.py").write_text(source, encoding="utf-8")
    return _Fixture(
        pkg=str(pkg_dir),
        abstract_line=_method_def_line(source, "AbstractProcessor", "process"),
        concrete_line=_method_def_line(source, "ConcreteProcessor", "process"),
    )


def test_ast_inspect_follows_abstract_method_to_concrete_override(
    abstract_pkg: _Fixture,
) -> None:
    """ast_context surfaces the pair; ast_inspect follows to the concrete override.

    The resolved target must be the concrete override symbol *and* its file/line,
    not merely a call that returned without error. Neutralising the follow logic
    (returning the abstract declaration, or nothing) collapses the concrete and
    abstract locations together and fails the final inequality assertion.
    """
    # ToolAstContext (ast_context) genuinely sees the abstract -> concrete pair.
    ctx = ContextTool().execute(path=abstract_pkg.pkg, depth=3)
    assert ctx.success, ctx.error
    assert ctx.text is not None
    assert "AbstractProcessor" in ctx.text
    assert "ConcreteProcessor" in ctx.text

    # ast_inspect follows to the concrete subclass override.
    concrete = InspectTool().execute(
        path=abstract_pkg.pkg, symbol="ConcreteProcessor.process"
    )
    assert concrete.success, concrete.error
    detail = concrete.data["symbol"]
    assert detail["name"] == "process"
    assert Path(detail["file"]).name == "abstract_following.py"
    assert detail["start_line"] == abstract_pkg.concrete_line

    # The abstract declaration lives on a different line: the follow genuinely
    # lands on the override, not on the abstract def.
    abstract = InspectTool().execute(
        path=abstract_pkg.pkg, symbol="AbstractProcessor.process"
    )
    assert abstract.success, abstract.error
    assert abstract.data["symbol"]["start_line"] == abstract_pkg.abstract_line
    assert detail["start_line"] != abstract.data["symbol"]["start_line"]


def test_ast_inspect_surfaces_method_abstractness(
    abstract_pkg: _Fixture,
) -> None:
    """AC1/AC6 (L4 06a5ca28-fb63): ast_inspect surfaces the real abstract kind.

    Reversed from the former pin that asserted the hardcoded ``function``
    default: a genuinely abstract method (ABC + @abstractmethod) must now report
    ``abstract``. NOT deleted -- this remains the AXM-1464 regression net.
    """
    result = InspectTool().execute(
        path=abstract_pkg.pkg, symbol="AbstractProcessor.process"
    )
    assert result.success, result.error
    # The method IS abstract (ABC + @abstractmethod) -> real kind surfaced.
    assert result.data["symbol"]["kind"] == "abstract", _KIND_L4_PIN


def test_ast_inspect_free_function_reports_function(
    abstract_pkg: _Fixture,
) -> None:
    """AC2: a top-level free function still reports ``function`` (non-regression)."""
    result = InspectTool().execute(path=abstract_pkg.pkg, symbol="free_transform")
    assert result.success, result.error
    assert result.data["symbol"]["kind"] == "function", _KIND_L4_PIN
