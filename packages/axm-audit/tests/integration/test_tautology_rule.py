"""Integration test: removing name-based opt-out does not regress.

Verifies axm-audit's own suite still passes.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import cast

import pytest

from axm_audit.core.rules.test_quality.tautology import TautologyRule

pytestmark = pytest.mark.integration

_BASELINE_PATH = (
    Path(__file__).parent.parent / "fixtures" / "tautology_baseline_axm_audit.json"
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def test_axm_audit_own_suite_no_regression() -> None:
    """AC4: TautologyRule on axm-audit produces no new STRENGTHEN."""
    project = _project_root()
    result = TautologyRule().check(project)
    verdicts = cast(list[dict[str, object]], result.metadata["verdicts"])
    strengthen_count = sum(1 for v in verdicts if v["verdict"] == "STRENGTHEN")

    if _BASELINE_PATH.exists():
        baseline = json.loads(_BASELINE_PATH.read_text())
        baseline_count = int(baseline.get("strengthen_count", 0))
    else:
        baseline_count = strengthen_count

    assert strengthen_count <= baseline_count, (
        f"STRENGTHEN findings increased: {strengthen_count} > baseline {baseline_count}"
    )


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip())


@pytest.fixture
def tautology_project(tmp_path: Path) -> Path:
    _write(
        tmp_path / "tests" / "test_taut.py",
        """
        def test_trivial():
            assert True
        """,
    )
    return tmp_path


def _make_project(tmp_path: Path, files: dict[str, str]) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "tests").mkdir(exist_ok=True)
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dedent(content))
    return tmp_path


def test_tautology_failed_populates_actionable_fields(
    tautology_project: Path,
) -> None:
    result = TautologyRule().check(tautology_project)
    assert result.passed is False
    assert result.text and "•" in result.text
    assert result.fix_hint and "behavioral" in result.fix_hint
    assert result.metadata is not None
    assert "verdicts" in result.metadata


def test_tautology_passed_omits_text_and_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    result = TautologyRule().check(tmp_path)
    assert result.passed is True
    assert result.text is None
    assert result.fix_hint is None


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
