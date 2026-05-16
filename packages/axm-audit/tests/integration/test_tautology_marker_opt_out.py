"""Integration tests for `pytest.mark.tautology_ok` end-to-end on a tmp project.

AC1, AC2, AC4, AC5: marker clears findings on real test trees.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule
from axm_audit.core.rules.test_quality.tautology import TautologyRule

pytestmark = pytest.mark.integration


def _make_project(tmp_path: Path, files: dict[str, str]) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "tests").mkdir(exist_ok=True)
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dedent(content))
    return tmp_path


def test_marker_clears_finding_end_to_end(tmp_path: Path) -> None:
    """AC2, AC4, AC5: tagged test produces a KEEP verdict; rule passes."""
    project = _make_project(
        tmp_path,
        {
            "tests/unit/test_x.py": """
                import pytest

                @pytest.mark.tautology_ok("mypy narrow")
                def test_x():
                    x = object()
                    assert isinstance(x, object)
            """,
        },
    )

    result = TautologyRule().check(project)

    assert result.passed is True
    verdicts = result.metadata["verdicts"]
    keep_verdicts = [v for v in verdicts if v["verdict"] == "KEEP"]
    assert keep_verdicts, "expected at least one KEEP verdict in metadata"


def test_file_level_pytestmark_clears_all_tests_in_file(tmp_path: Path) -> None:
    """AC1: file-level pytestmark covers every test in the file only."""
    project = _make_project(
        tmp_path,
        {
            "tests/unit/test_tagged.py": """
                import pytest

                pytestmark = pytest.mark.tautology_ok

                def test_a():
                    x = object()
                    assert isinstance(x, object)

                def test_b():
                    y = object()
                    assert isinstance(y, object)
            """,
            "tests/unit/test_other.py": """
                def test_c():
                    z = object()
                    assert isinstance(z, object)
            """,
        },
    )

    result = TautologyRule().check(project)
    verdicts = result.metadata["verdicts"]

    tagged = [v for v in verdicts if v["file"].endswith("test_tagged.py")]
    other = [v for v in verdicts if v["file"].endswith("test_other.py")]

    assert tagged, "expected verdicts on tagged file"
    assert all(v["verdict"] == "KEEP" for v in tagged)
    assert other, "expected verdicts on untagged sibling"
    assert all(v["verdict"] != "KEEP" for v in other)


def test_marker_does_not_suppress_other_test_quality_rules(tmp_path: Path) -> None:
    """AC2: marker is tautology-scoped — other rules still fire."""
    project = _make_project(
        tmp_path,
        {
            "src/pkg/_internal.py": "def _secret():\n    return 42\n",
            "tests/unit/test_x.py": """
                import pytest
                from pkg._internal import _secret

                @pytest.mark.tautology_ok
                def test_x():
                    assert _secret() == 42
            """,
        },
    )

    result = PrivateImportsRule().check(project)

    assert result.passed is False
