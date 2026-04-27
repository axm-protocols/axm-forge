from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.complexity import ComplexityRule

pytestmark = pytest.mark.integration


def _function_cc11(name: str) -> str:
    """Build a function with cyclomatic complexity == 11 (grade C)."""
    lines = [f"def {name}(x):"]
    for i in range(10):
        lines.append(f"    if x == {i}:")
        lines.append("        return 0")
    lines.append("    return 1")
    return "\n".join(lines) + "\n"


def test_subprocess_path_uses_grade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """AC2: subprocess radon path flags CC=11 with rank='C'."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text(_function_cc11("feature"), encoding="utf-8")

    monkeypatch.setattr(
        "axm_audit.core.rules.complexity._try_import_radon",
        lambda: None,
    )
    monkeypatch.chdir(tmp_path)

    rule = ComplexityRule()
    result = rule.check(tmp_path)

    assert result.details["high_complexity_count"] == 1
    offenders = result.details["top_offenders"]
    assert offenders[0]["rank"] == "C"
