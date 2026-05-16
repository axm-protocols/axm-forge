"""Integration tests: FileNamingRule.check populates CheckResult.text.

Drives the rule end-to-end on a real on-disk project to exercise the
public boundary that the unit tests intentionally bypass.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.file_naming import FileNamingRule

pytestmark = pytest.mark.integration


def _scaffold_package(root: Path) -> None:
    """Minimal package layout the file-naming rule accepts."""
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    src = root / "src" / "sample"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "core.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "unit").mkdir()
    (root / "tests" / "integration").mkdir()


def test_check_populates_text_field(tmp_path: Path) -> None:
    """AC1 — CheckResult.text is populated when findings exist."""
    _scaffold_package(tmp_path)
    bad_warning = tmp_path / "tests" / "integration" / "test_warn_scenario.py"
    bad_warning.write_text(
        "from sample.core import add\n"
        "\ndef test_x() -> None:\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    bad_info = tmp_path / "tests" / "integration" / "test_info_scenario.py"
    bad_info.write_text(
        "def test_y() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    result = FileNamingRule().check(tmp_path)

    assert isinstance(result.text, str)
    assert result.text
    assert (
        "test_warn_scenario.py" in result.text or "test_info_scenario.py" in result.text
    )


def test_check_text_is_none_when_passing(tmp_path: Path) -> None:
    """AC5 — CheckResult.text is None when no findings (passing case)."""
    _scaffold_package(tmp_path)
    canonical = tmp_path / "tests" / "unit" / "test_core.py"
    canonical.write_text(
        "from sample.core import add\n"
        "\ndef test_add() -> None:\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    result = FileNamingRule().check(tmp_path)

    assert result.passed is True
    assert result.text is None


def test_self_audit_text_under_size_threshold() -> None:
    """AC6 — self-audit on axm-audit produces text well under 4 KB."""
    package_root = Path(__file__).resolve().parents[2]

    result = FileNamingRule().check(package_root)

    if result.text is None:
        pytest.skip("axm-audit has no FILE_NAMING findings; size cap trivially met")
    assert len(result.text) < 4_000
