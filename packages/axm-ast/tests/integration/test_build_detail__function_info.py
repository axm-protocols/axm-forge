from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.models import FunctionInfo, ParamInfo


@pytest.fixture
def _sample_function() -> FunctionInfo:
    return FunctionInfo(
        name="my_func",
        line_start=10,
        line_end=20,
        signature="(x: int, y: str) -> bool",
        params=[
            ParamInfo(name="x", annotation="int", default=None),
            ParamInfo(name="y", annotation="str", default="'hello'"),
        ],
        return_type="bool",
        docstring="A function.",
    )


class TestBuildDetailIntegration:
    """Integration: build_detail reads real files for source inclusion."""

    def test_source_included_when_requested(
        self, _sample_function: FunctionInfo, tmp_path: Path
    ) -> None:
        from axm_ast.tools.inspect_detail import build_detail

        src_file = tmp_path / "mod.py"
        lines = [f"line {i}" for i in range(1, 25)]
        src_file.write_text("\n".join(lines))
        detail = build_detail(
            _sample_function,
            file="mod.py",
            abs_path=str(src_file),
            source=True,
        )
        assert "source" in detail
        assert "line 10" in detail["source"]
