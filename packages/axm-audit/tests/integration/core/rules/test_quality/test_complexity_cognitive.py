from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.complexity import ComplexityRule

pytestmark = pytest.mark.integration


_AXM_AUDIT_ROOT = Path(__file__).resolve().parents[5]
_FORGE = _AXM_AUDIT_ROOT.parent.parent
_AXM_AST = _FORGE / "packages" / "axm-ast"
_AXM_AUDIT = _FORGE / "packages" / "axm-audit"


@pytest.fixture
def rule() -> ComplexityRule:
    return ComplexityRule()


@pytest.mark.skipif(
    not (_AXM_AST / "src").exists(),
    reason="axm-ast/src not available in this checkout",
)
def test_axm_ast_cognitive_offenders_count(rule: ComplexityRule) -> None:
    result = rule.check(_AXM_AST)
    assert result.details["high_complexity_count"] == 13


@pytest.mark.skipif(
    not (_AXM_AUDIT / "src").exists(),
    reason="axm-audit/src not available in this checkout",
)
def test_axm_audit_cognitive_offenders_count(rule: ComplexityRule) -> None:
    result = rule.check(_AXM_AUDIT)
    assert result.details["high_complexity_count"] == 5


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
    real_which = complexity_module.shutil.which

    def fake_which(name: str, *args: object, **kwargs: object) -> str | None:
        if name == "complexipy":
            return None
        return real_which(name, *args, **kwargs)

    monkeypatch.setattr(complexity_module.shutil, "which", fake_which)

    result = rule.check(tmp_path)
    assert result.passed is not None
    assert result.severity is not None
    msg = (result.message or "").lower()
    assert "cognitive" in msg or "complexipy" in msg


def test_claude_md_documents_double_constraint() -> None:
    claude_md = Path.home() / ".claude" / "CLAUDE.md"
    if not claude_md.exists():
        pytest.skip("~/.claude/CLAUDE.md not present")
    content = claude_md.read_text(encoding="utf-8")
    assert "Cog<15" in content or "Cognitive < 15" in content
    assert "C901" in content
