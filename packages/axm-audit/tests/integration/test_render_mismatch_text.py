"""Unit tests for ``pyramid_level.render_mismatch_text`` and ``relpath``."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.test_quality.pyramid_level import (
    Finding,
    render_mismatch_text,
)


def _finding(path: str, function: str = "test_x") -> Finding:
    return Finding(
        path=path,
        function=function,
        level="unit",
        reason="r",
        current_level="integration",
        has_real_io=False,
        has_subprocess=False,
    )


def test_render_uses_relative_paths(tmp_path: Path) -> None:
    f = _finding(str(tmp_path / "tests" / "integration" / "test_a.py"))
    text = render_mismatch_text([f], tmp_path)
    assert str(tmp_path) not in text
    assert "tests/integration/test_a.py:test_x integration→unit (r)" in text


def test_render_outside_keeps_absolute(tmp_path: Path) -> None:
    abs_outside = "/totally/outside/test_b.py"
    f = _finding(abs_outside, function="test_y")
    text = render_mismatch_text([f], tmp_path)
    assert abs_outside in text


def test_render_caps_with_more_suffix(tmp_path: Path) -> None:
    findings = [
        _finding(str(tmp_path / f"tests/unit/test_{i}.py"), f"test_{i}")
        for i in range(25)
    ]
    text = render_mismatch_text(findings, tmp_path)
    assert "(+5 more)" in text
