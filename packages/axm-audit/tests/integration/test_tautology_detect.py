from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.tautology import TautologyRule
from axm_audit.models.results import Severity

pytestmark = pytest.mark.integration


def test_severity_warning(tmp_path: Path) -> None:
    f = tmp_path / "test_sample.py"
    f.write_text("def test_foo():\n    assert True\n")
    rule = TautologyRule()
    result = rule.check(tmp_path)
    assert result.severity == Severity.WARNING


def test_metadata_verdicts_shape(tmp_path: Path) -> None:
    f = tmp_path / "test_sample.py"
    f.write_text(
        "def test_a():\n"
        "    assert True\n"
        "\n"
        "def test_b():\n"
        "    x = 1\n"
        "    assert x == x\n"
    )
    rule = TautologyRule()
    result = rule.check(tmp_path)
    verdicts = result.metadata["verdicts"]
    assert isinstance(verdicts, list)
    assert len(verdicts) == 2
    expected_keys = {"test", "line", "pattern", "rule", "verdict", "reason"}
    for v in verdicts:
        assert isinstance(v, dict)
        assert expected_keys.issubset(v.keys())
