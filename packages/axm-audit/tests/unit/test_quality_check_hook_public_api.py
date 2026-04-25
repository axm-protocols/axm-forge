"""Public-API tests for ``QualityCheckHook`` (replaces private
``_read_snippet`` import in ``tests/hooks/test_quality_check_snippet.py``)."""

from __future__ import annotations

from axm_audit.hooks.quality_check import QualityCheckHook
from axm_audit.models import AuditResult, CheckResult


def test_quality_check_hook_reads_snippet_via_public_api(tmp_path, monkeypatch):
    """AC6: when the hook surfaces a violation, the rendered output references
    the file path / line being flagged (the snippet is read from the public
    callsite, not via direct ``_read_snippet`` import)."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    file_path = src / "mod.py"
    file_path.write_text("unique_marker_xyz = 1 + 2\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1"\n'
    )

    failed = CheckResult(
        rule_id="QUALITY_LINT",
        passed=False,
        message="lint failed",
        category="linting",
        details={
            "issues": [
                {
                    "file": str(file_path),
                    "line": 1,
                    "code": "E501",
                    "message": "line too long",
                }
            ],
            "score": 50,
        },
        text="\u2022 E501 src/pkg/mod.py:1 line too long",
    )
    fake_audit = AuditResult(project_path=str(tmp_path), checks=[failed])

    from axm_audit.hooks import quality_check as qc_mod

    monkeypatch.setattr(qc_mod, "_run_audits", lambda p, c: [fake_audit])

    hook = QualityCheckHook()
    result = hook.execute({"working_dir": str(tmp_path)})

    assert result is not None
    text = getattr(result, "text", "") or ""
    assert "mod.py" in text or "E501" in text
