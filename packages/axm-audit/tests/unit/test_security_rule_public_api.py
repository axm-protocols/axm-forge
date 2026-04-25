"""Public-API tests for ``SecurityRule`` (replaces private
``_build_security_result`` import in ``tests/core/rules/test_security_text.py``)."""

from __future__ import annotations

from axm_audit.core.rules.security import SecurityRule


def test_security_rule_text_format(tmp_path, monkeypatch):
    """AC2: ``SecurityRule().check()`` returns a ``CheckResult`` whose ``text``
    follows the expected per-issue line format."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "module.py").write_text("password = 'hardcoded123'\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1"\n'
    )

    fake_bandit = {
        "results": [
            {
                "filename": str(src / "module.py"),
                "line_number": 1,
                "issue_severity": "MEDIUM",
                "issue_text": "Possible hardcoded password",
                "test_id": "B105",
            }
        ]
    }

    from axm_audit.core.rules import security as sec_mod

    monkeypatch.setattr(
        sec_mod, "_run_bandit", lambda src_path, project_path: fake_bandit
    )

    result = SecurityRule().check(tmp_path)

    assert result.rule_id == "QUALITY_SECURITY"
    assert result.text is not None
    # Text references the issue location and identifier.
    assert "B105" in result.text or "hardcoded" in result.text.lower()
    assert "module.py" in result.text
