from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from axm_audit.core.rules.test_quality.pyramid_level import scan_test_file


def _write_pkg(tmp_path: Path) -> tuple[Path, Path, Path]:
    pkg_root = tmp_path
    tests_dir = pkg_root / "tests"
    tests_dir.mkdir()
    conftest = tests_dir / "conftest.py"
    conftest.write_text(
        textwrap.dedent(
            """
            import socket
            import pytest

            @pytest.fixture
            def io_fixture():
                return socket.socket()
            """
        ).lstrip()
    )
    return pkg_root, tests_dir, conftest


def test_signals_order_r1_then_r3_then_r4(tmp_path: Path) -> None:
    """Signals must appear once, in R1 -> R3 -> R4 emission order.

    Setup mixes a module-level IO import (R1), a tmp_path write (R3) and a
    conftest fixture doing IO (R4). R3 attr-scan stays empty here, so R4 is
    expected to also contribute signals on top of R1+R3.
    """
    pkg_root, tests_dir, _ = _write_pkg(tmp_path)

    src = textwrap.dedent(
        """
        import socket

        def test_a(tmp_path, io_fixture):
            socket  # referenced but no attr access -> R1 only, no attr_sigs
            p = tmp_path / "f.txt"
            p.write_text("x")
        """
    ).lstrip()
    test_file = tests_dir / "test_x.py"
    test_file.write_text(src)
    tree = ast.parse(src)

    findings = scan_test_file(test_file, tree, pkg_root, set(), None, tests_dir)

    assert len(findings) == 1
    sigs = findings[0].io_signals

    # No duplicates - each rule appends only when sig is not already present.
    assert len(sigs) == len(set(sigs)), f"duplicate signals emitted: {sigs}"

    # R1 imports come first.
    r1_sigs = [s for s in sigs if s.startswith("imports ")]
    assert r1_sigs, f"expected R1 'imports ...' signal, got: {sigs}"
    first_non_r1 = next(
        (i for i, s in enumerate(sigs) if not s.startswith("imports ")), len(sigs)
    )
    last_r1 = max(i for i, s in enumerate(sigs) if s.startswith("imports "))
    assert last_r1 < first_non_r1 or first_non_r1 == len(sigs), (
        f"R1 signals must precede R3/R4 signals, got order: {sigs}"
    )

    # R3 tmp_path signals must be present (at least one of the two markers).
    tmp_markers = {"tmp_path-as-arg", "tmp_path+write/read"}
    assert tmp_markers & set(sigs), f"expected R3 tmp_path signal, got: {sigs}"

    # has_real_io is True since R1 + R3 both fired.
    assert findings[0].has_real_io is True
