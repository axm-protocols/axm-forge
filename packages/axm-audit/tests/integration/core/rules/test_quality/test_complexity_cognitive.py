from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from axm_audit.core.rules.complexity import ComplexityRule

pytestmark = pytest.mark.integration


@pytest.fixture
def rule() -> ComplexityRule:
    return ComplexityRule()


def test_complexipy_missing_does_not_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rule: ComplexityRule,
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "m.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    from axm_audit.core.rules import complexity as complexity_module

    monkeypatch.setattr(complexity_module, "_try_import_complexipy", lambda: None)
    real_which = shutil.which

    def fake_which(name: str) -> str | None:
        if name == "complexipy":
            return None
        return real_which(name)

    monkeypatch.setattr(shutil, "which", fake_which)

    result = rule.check(tmp_path)
    assert result.passed is not None
    assert result.severity is not None
    msg = (result.message or "").lower()
    assert "cognitive" in msg or "complexipy" in msg
