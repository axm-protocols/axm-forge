from __future__ import annotations

import ast
from pathlib import Path

from axm_audit.core.fix.cst_rewrite import (
    _project_import_index,
    _synth_import_from_helpers,
    invalidate_import_index,
)
from axm_audit.core.fix.extract_helpers import extract_shared_helpers_once


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_project_import_index_reads_namespaced_suite(tmp_path: Path) -> None:
    """The import cache scans the canonical tests_<pkg> suite."""
    project = tmp_path / "axm-sample"
    test_file = project / "tests_axm_sample" / "unit" / "test_feature.py"
    _write(test_file, "from sample.helpers import shared\n")

    invalidate_import_index(project)
    try:
        index = _project_import_index(project)
    finally:
        invalidate_import_index(project)

    assert "shared" in index


def test_synth_import_uses_namespaced_suite_module(tmp_path: Path) -> None:
    """Synthesized helper imports target the resolved suite, not tests/."""
    project = tmp_path / "axm-sample"
    helpers = project / "tests_axm_sample" / "unit" / "_helpers.py"
    target = project / "tests_axm_sample" / "unit" / "test_feature.py"
    _write(helpers, "def shared() -> int:\n    return 1\n")
    _write(target, "def test_feature() -> None:\n    assert shared() == 1\n")

    result = _synth_import_from_helpers("shared", project, target)

    assert result is not None
    statement, enclosing = result
    assert enclosing is None
    assert ast.unparse(statement) == (
        "from tests_axm_sample.unit._helpers import shared"
    )


def test_extract_shared_helpers_reads_namespaced_suite(tmp_path: Path) -> None:
    """Duplicate helpers are promoted inside the canonical tests_<pkg> suite."""
    project = tmp_path / "axm-sample"
    tier = project / "tests_axm_sample" / "integration"
    helper = "def _shared(x):\n    return x * 2\n\n\n"
    _write(
        tier / "test_a.py",
        helper + "def test_a():\n    assert _shared(1) == 2\n",
    )
    _write(
        tier / "test_b.py",
        helper + "def test_b():\n    assert _shared(2) == 4\n",
    )

    messages = extract_shared_helpers_once(project)

    assert (tier / "_helpers.py").is_file()
    assert any("extracted helper" in message for message in messages)
