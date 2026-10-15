"""Catalog guidance must cover the rule's observed access mechanisms."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from axm_audit.core.auditor import get_rules_for_category
from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule


@pytest.mark.integration
def test_catalog_covers_detected_private_access(tmp_path: Path) -> None:
    source = tmp_path / "src/tiny"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("def _private():\n    return 1\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_api.py").write_text("import tiny\ntiny._private()\n")
    result = PrivateImportsRule().check(tmp_path)
    assert not result.passed
    assert result.details is not None
    observed = {f["access_kind"] for f in result.details["findings"]}
    assert len(observed) == 1
    rule = next(r for r in get_rules_for_category(None) if r.rule_id == result.rule_id)
    description = (inspect.getdoc(type(rule)) or "").split("\n\n", 1)[0]
    vocabulary = set(re.findall(r"[a-z]+", description.lower()))
    advertised = {
        kind
        for kind in ("import", "attribute")
        if kind in vocabulary or kind + "s" in vocabulary
    }
    assert observed <= advertised
