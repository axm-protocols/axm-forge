"""Public-API tests for ``LintingRule`` (replaces private
``_get_audit_targets`` import in ``tests/core/rules/test_quality.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from axm_audit.core.rules.quality import LintingRule


@dataclass
class _FakeProc:
    stdout: str = "[]"
    stderr: str = ""
    returncode: int = 0


def test_linting_rule_targets_src_only(tmp_path, monkeypatch):
    """AC3: ``LintingRule().check()`` invokes ruff on ``src/`` (and ``tests/``
    if present); never on the project root or other arbitrary paths."""
    src = tmp_path / "src" / "pkg"
    tests = tmp_path / "tests"
    src.mkdir(parents=True)
    tests.mkdir()
    (src / "__init__.py").write_text("")
    (src / "module.py").write_text("x = 1\n")
    (tests / "test_x.py").write_text("def test_x():\n    assert True\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1"\n'
    )
    # Sentinel file that should NOT be linted.
    (tmp_path / "sentinel.py").write_text("y = 1\n")

    captured: dict[str, list[str]] = {}

    def fake_run(cmd, project_path, **kwargs):
        captured["cmd"] = list(cmd)
        return _FakeProc()

    from axm_audit.core.rules import quality as q_mod

    monkeypatch.setattr(q_mod, "run_in_project", fake_run)

    LintingRule().check(tmp_path)

    cmd = captured["cmd"]
    # ['ruff', 'check', '--output-format=json', *targets]
    assert cmd[:3] == ["ruff", "check", "--output-format=json"]
    targets = cmd[3:]
    assert targets, "ruff should be invoked on at least one target"
    joined = " ".join(targets)
    assert "src" in joined
    assert "sentinel.py" not in joined
