"""Split from ``test_quality_rule_io.py``."""

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("rule_cls", "source", "collection_key"),
    [
        pytest.param(
            "LintingRule",
            "import os\nimport sys\n",
            "issues",
            id="lint_issue_entry_schema",
        ),
    ],
)
def test_issue_entry_schema(
    tmp_path: Path, rule_cls: str, source: str, collection_key: str
) -> None:
    """Each issue/error entry must have file, line, code, message keys."""
    from axm_audit.core.rules import quality as q

    src = tmp_path / "src"
    src.mkdir()
    (src / "bad.py").write_text(source)

    rule = getattr(q, rule_cls)()
    result = rule.check(tmp_path)
    assert result.details is not None
    for entry in result.details[collection_key]:
        assert "file" in entry
        assert "line" in entry
        assert "code" in entry
        assert "message" in entry


@pytest.mark.parametrize(
    ("rule_cls", "source", "collection_key"),
    [
        pytest.param(
            "TypeCheckRule",
            'def add(a: int, b: int) -> int:\n    return "not an int"\n',
            "errors",
            id="typecheck_error_entry_schema",
        ),
    ],
)
def test_error_entry_schema(
    tmp_path: Path, rule_cls: str, source: str, collection_key: str
) -> None:
    """Each error entry must have file, line, message, code keys."""
    from axm_audit.core.rules import quality as q

    src = tmp_path / "src"
    src.mkdir()
    (src / "bad.py").write_text(source)

    rule = getattr(q, rule_cls)()
    result = rule.check(tmp_path)
    assert result.details is not None
    for entry in result.details[collection_key]:
        assert "file" in entry
        assert "line" in entry
        assert "message" in entry
        assert "code" in entry
