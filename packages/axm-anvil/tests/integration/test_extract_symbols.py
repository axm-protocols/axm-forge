from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_anvil.core.extract import extract_symbols

pytestmark = pytest.mark.integration


def test_extract_creates_new_module_with_deps(tmp_path: Path) -> None:
    """AC2: extracting into a non-existent target creates the module with the
    moved block plus its transitive imports/helpers."""
    src = tmp_path / "src.py"
    src.write_text(
        textwrap.dedent(
            """\
            import math


            def _double(x: int) -> int:
                return x * 2


            def area(r: int) -> int:
                return _double(int(math.pi)) * r
            """
        )
    )
    tgt = tmp_path / "geometry.py"
    assert not tgt.exists()

    plan = extract_symbols(
        src,
        tgt,
        ["area"],
        workspace_root=tmp_path,
    )

    assert "area" in plan.moved_names
    assert tgt.exists()
    target_text = tgt.read_text()
    assert "def area" in target_text
    # Transitive helper copied alongside.
    assert "_double" in target_text
    # Required import copied.
    assert "import math" in target_text


def test_extract_rewrites_callers_to_new_module(tmp_path: Path) -> None:
    """AC3: cross-file callers of an extracted symbol are rewritten from the
    old module to the new one."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    src = pkg / "old.py"
    src.write_text(
        textwrap.dedent(
            """\
            def shout(msg: str) -> str:
                return msg.upper()
            """
        )
    )
    caller = pkg / "caller.py"
    caller.write_text(
        textwrap.dedent(
            """\
            from pkg.old import shout


            def greet() -> str:
                return shout("hi")
            """
        )
    )
    tgt = pkg / "new.py"

    plan = extract_symbols(
        src,
        tgt,
        ["shout"],
        workspace_root=tmp_path,
    )

    assert "shout" in plan.moved_names
    caller_text = caller.read_text()
    assert "from pkg.new import shout" in caller_text
    assert "from pkg.old import shout" not in caller_text


def test_extract_dry_run_no_write(tmp_path: Path) -> None:
    """AC4: a dry-run computes the plan without creating the target module."""
    src = tmp_path / "src.py"
    src.write_text(
        textwrap.dedent(
            """\
            def foo() -> int:
                return 1
            """
        )
    )
    tgt = tmp_path / "new.py"

    plan = extract_symbols(
        src,
        tgt,
        ["foo"],
        dry_run=True,
        workspace_root=tmp_path,
    )

    assert "foo" in plan.moved_names
    assert not tgt.exists()
