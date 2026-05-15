"""Integration tests on synthetic project layouts (AC3, AC4, AC5)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.no_package_symbol import (
    NoPackageSymbolRule,
)

pytestmark = pytest.mark.integration


def _make_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "synpkg"
    (pkg / "src" / "pkg").mkdir(parents=True)
    (pkg / "src" / "pkg" / "__init__.py").write_text("def fn() -> int:\n    return 1\n")
    (pkg / "tests" / "integration").mkdir(parents=True)
    (pkg / "tests" / "e2e").mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "pkg"
            version = "0.0.0"

            [project.scripts]
            pkg-cli = "pkg.cli:main"
            """
        ).strip()
    )
    return pkg


def test_mislocated_e2e_test_flagged(tmp_path: Path) -> None:
    """AC4: e2e test exercising only Python symbol → MISLOCATED_INTEGRATION."""
    pkg = _make_pkg(tmp_path)
    (pkg / "tests" / "e2e" / "test_x.py").write_text(
        "from pkg import fn\n\ndef test_x():\n    assert fn() == 1\n"
    )
    result = NoPackageSymbolRule().check(pkg)
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["verdict"] == "MISLOCATED_INTEGRATION"


def test_no_symbol_test_flagged(tmp_path: Path) -> None:
    """AC5: integration test with no symbol and no CLI → NO_PACKAGE_SYMBOL."""
    pkg = _make_pkg(tmp_path)
    (pkg / "README.md").write_text("hello")
    (pkg / "tests" / "integration" / "test_x.py").write_text(
        "from pathlib import Path\n\n"
        "def test_x():\n"
        "    p = Path(__file__).parent.parent.parent\n"
        "    text = p.joinpath('README.md').read_text()\n"
        "    assert 'hello' in text\n"
    )
    result = NoPackageSymbolRule().check(pkg)
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["verdict"] == "NO_PACKAGE_SYMBOL"


def test_legitimate_e2e_passes(tmp_path: Path) -> None:
    """AC3: e2e test invoking declared CLI → no finding."""
    pkg = _make_pkg(tmp_path)
    (pkg / "tests" / "e2e" / "test_x.py").write_text(
        "import subprocess\n\n"
        "def test_x():\n"
        '    subprocess.run(["pkg-cli", "do"], check=True)\n'
    )
    result = NoPackageSymbolRule().check(pkg)
    assert result.passed is True
    assert result.details["findings"] == []


def test_legitimate_integration_passes(tmp_path: Path) -> None:
    """AC3: integration test importing first-party symbol → no finding."""
    pkg = _make_pkg(tmp_path)
    (pkg / "tests" / "integration" / "test_x.py").write_text(
        "from pkg import fn\n\ndef test_x():\n    assert fn() == 1\n"
    )
    result = NoPackageSymbolRule().check(pkg)
    assert result.passed is True
    assert result.details["findings"] == []
