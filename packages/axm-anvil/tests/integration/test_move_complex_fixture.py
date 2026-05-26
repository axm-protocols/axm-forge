from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parent / "fixtures"


def test_move_complex_fixture(tmp_path: Path) -> None:
    src = tmp_path / "source_complex.py"
    tgt = tmp_path / "target_complex.py"
    shutil.copy(FIXTURES / "source_complex.py", src)
    shutil.copy(FIXTURES / "target_complex.py", tgt)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    move_symbols(
        src,
        tgt,
        ["TestAnalyzeModuleUnit", "TestAnalyzePackageIntegration"],
        dry_run=False,
    )
    target_text = tgt.read_text()
    assert "class TestAnalyzeModuleUnit" in target_text
    assert "class TestAnalyzePackageIntegration" in target_text
    assert "from unittest.mock" in target_text
    assert "import pytest" in target_text
    assert "from mylib.core.models import ModuleInfo" in target_text
    assert "SAMPLE_PKG" in target_text

    source_text = src.read_text()
    assert "class StaysHere" in source_text
