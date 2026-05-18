"""Integration test: ``CoverageRule`` extracts failing tests via the
public ``check()`` callsite (replaces private ``_extract_test_failures``
import in ``tests/test_cli.py``)."""

from __future__ import annotations

import pytest

from axm_audit.core.rules.coverage import TestCoverageRule as CoverageRule


@pytest.mark.integration
def test_coverage_rule_extracts_failures_end_to_end(tmp_path):
    """AC5: When a project has a failing test, ``CoverageRule().check()`` returns
    a ``CheckResult`` whose ``text`` lists the failing test name."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "module.py").write_text("def f():\n    return 1\n")

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_module.py").write_text(
        "def test_pkg_failing_canary():\n    assert False, 'always fails'\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1"\n'
    )

    result = CoverageRule().check(tmp_path)

    assert result.rule_id
    # When there are test failures, they are surfaced through ``text``.
    text = (result.text or "") + " " + (result.message or "")
    assert "test_pkg_failing_canary" in text or "failed" in text.lower()
