"""E2E parity test for the legacy fix-proto script shim."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.e2e
@pytest.mark.no_package_symbol_ok
def test_legacy_script_shim_still_works(tmp_path: Path) -> None:
    """AC3: legacy `scripts/test_orga/tuple_fix_proto.py` shim.

    Verify the shim remains a working entry point.
    """
    tmp_pkg = tmp_path / "pkg"
    tmp_pkg.mkdir()
    (tmp_pkg / "tests").mkdir()

    script = PACKAGE_ROOT / "scripts" / "test_orga" / "tuple_fix_proto.py"

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "python", str(script), str(tmp_pkg)],  # noqa: S607
        cwd=PACKAGE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Pipeline (dry-run" in result.stdout
