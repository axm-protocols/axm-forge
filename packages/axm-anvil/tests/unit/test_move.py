from __future__ import annotations

from pathlib import Path

import libcst as cst

from axm_anvil._cst.blocks import Block, extract_blocks
from axm_anvil.core.move import (
    PYTEST_BUILTIN_FIXTURES,
    detect_fixture_dependencies,
    move_symbols,
)
from axm_anvil.tools.move import MoveTool


def _write_pair(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Foo():\n    return 1\n")
    tgt.write_text("")
    return src, tgt


def test_execute_rename_invalid_json_returns_error(tmp_path: Path) -> None:
    """AC2: invalid JSON in rename returns success=False without raising."""
    src, tgt = _write_pair(tmp_path)
    result = MoveTool().execute(
        path=str(tmp_path),
        symbols="Foo",
        from_file=str(src),
        to_file=str(tgt),
        rename="{bad",
    )
    assert result.success is False
    assert "json" in (result.error or "").lower()


def test_execute_rename_with_reexport_errors(tmp_path: Path) -> None:
    """AC3: rename combined with reexport surfaces the ValueError as a result."""
    src, tgt = _write_pair(tmp_path)
    result = MoveTool().execute(
        path=str(tmp_path),
        symbols="Foo",
        from_file=str(src),
        to_file=str(tgt),
        rename='{"Foo":"Bar"}',
        reexport=True,
    )
    assert result.success is False
    assert "incompatible" in (result.error or "").lower()


def test_insert_after_none_appends_at_end(tmp_path: Path) -> None:
    """AC2: insert_after=None preserves the historical end-append contract."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Moved():\n    return 1\n")
    tgt.write_text("def Anchor():\n    return 0\n\n\ndef Tail():\n    return 2\n")

    plan = move_symbols(src, tgt, ["Moved"], dry_run=True, insert_after=None)

    text = plan.target_text_new
    assert text.index("def Moved") > text.index("def Anchor")
    assert text.index("def Moved") > text.index("def Tail")


def test_insert_after_absent_warns_and_appends(tmp_path: Path) -> None:
    """AC3: an absent insert_after anchor appends at end and adds a warning."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Moved():\n    return 1\n")
    tgt.write_text("def Anchor():\n    return 0\n")

    plan = move_symbols(src, tgt, ["Moved"], dry_run=True, insert_after="NoSuch")

    text = plan.target_text_new
    assert text.index("def Moved") > text.index("def Anchor")
    assert any("NoSuch" in w for w in plan.warnings)


def _blocks_for(source: str, names: list[str]) -> list[Block]:
    """Parse ``source`` in memory and extract the requested top-level blocks."""
    return extract_blocks(cst.parse_module(source), names)


def test_builtin_fixture_never_warns() -> None:
    """AC1: a moved test using only the builtin ``tmp_path`` fixture is not
    flagged as a non-builtin fixture dependency (in-memory detection)."""
    assert "tmp_path" in PYTEST_BUILTIN_FIXTURES
    blocks = _blocks_for("def test_x(tmp_path):\n    return tmp_path\n", ["test_x"])

    used = detect_fixture_dependencies(blocks, local_names=set())

    assert "tmp_path" not in used
    assert used == set()


def test_fixture_usage_detected() -> None:
    """AC2: a moved ``def test_x(my_fixture)`` whose parameter is neither a
    builtin nor a locally-resolvable name is identified as a fixture
    dependency (in-memory detection, no filesystem I/O)."""
    blocks = _blocks_for("def test_x(my_fixture):\n    return my_fixture\n", ["test_x"])

    used = detect_fixture_dependencies(blocks, local_names=set())

    assert "my_fixture" in used


def test_fixture_param_resolvable_as_local_excluded() -> None:
    """AC2: a test parameter whose name is also a local/imported symbol is not
    treated as a fixture dependency."""
    blocks = _blocks_for("def test_x(helper):\n    return helper\n", ["test_x"])

    used = detect_fixture_dependencies(blocks, local_names={"helper"})

    assert "helper" not in used


def test_fixture_self_and_defaults_excluded() -> None:
    """AC2: ``self`` and parameters carrying a default are never fixtures."""
    blocks = _blocks_for(
        "class C:\n    def test_m(self, real_fixture, opt=1):\n"
        "        return real_fixture\n",
        ["C"],
    )

    used = detect_fixture_dependencies(blocks, local_names=set())

    assert "self" not in used
    assert "opt" not in used
