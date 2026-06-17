from __future__ import annotations

import textwrap
from pathlib import Path

from axm_anvil.tools.extract import ExtractTool


def test_name_is_ast_extract() -> None:
    """AC1: the tool exposes the ``ast_extract`` registry name."""
    assert ExtractTool().name == "ast_extract"


def test_collision_returns_failure(tmp_path: Path) -> None:
    """AC4: extracting into a pre-existing module that already defines a
    homonymous symbol fails instead of silently overwriting."""
    src = tmp_path / "src.py"
    src.write_text(
        textwrap.dedent(
            """\
            def foo() -> int:
                return 1
            """
        )
    )
    # Target already exists AND defines `foo` -> collision.
    tgt = tmp_path / "dst.py"
    tgt.write_text(
        textwrap.dedent(
            """\
            def foo() -> int:
                return 99
            """
        )
    )

    result = ExtractTool().execute(
        path=str(tmp_path),
        from_file="src.py",
        to_file="dst.py",
        symbols="foo",
    )

    assert result.success is False
    # The pre-existing target must not have been clobbered.
    assert "return 99" in tgt.read_text()


def test_result_data_shape(tmp_path: Path) -> None:
    """AC5: a dry-run extract returns the same data shape as ``ast_move``:
    extracted symbols, copied dependencies, callers updated, created file."""
    src = tmp_path / "src.py"
    src.write_text(
        textwrap.dedent(
            """\
            import math


            def helper(x: int) -> int:
                return x * 2


            def foo() -> int:
                return helper(int(math.pi))
            """
        )
    )

    result = ExtractTool().execute(
        path=str(tmp_path),
        from_file="src.py",
        to_file="pkg/new.py",
        symbols="foo",
        dry_run=True,
    )

    assert result.success is True
    assert result.data is not None
    data = result.data
    moved_names = {entry["symbol"] for entry in data["moved"]}
    assert "foo" in moved_names
    assert "dependencies_copied" in data
    assert "callers_updated" in data
    assert "files_modified" in data
    # The to-be-created module is part of the reported modified files.
    assert any("new.py" in str(f) for f in data["files_modified"])
