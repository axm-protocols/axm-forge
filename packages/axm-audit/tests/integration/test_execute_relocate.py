"""Integration tests for execute_relocate (real fs + git + libcst + anvil)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.fix.models import FileOp
from axm_audit.core.fix.stages_execute import execute_relocate

pytestmark = pytest.mark.integration


def _op(
    kind: str,
    source: Path,
    target: Path | list[Path],
    *,
    split_map: dict[str, list[str]] | None = None,
) -> FileOp:
    return FileOp(
        kind=kind,
        source=source,
        target=target,
        rationale="r",
        source_rule="X",
        split_map=split_map,
    )


def test_execute_relocate_moves_file_across_tiers(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """RELOCATE git-moves a unit test into integration when target is free."""
    pkg = make_test_pkg(
        {
            "src/pkg/a.py": "def a():\n    return 1\n",
            "tests/__init__.py": "",
            "tests/unit/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/unit/test_a.py": (
                "from pkg.a import a\n\ndef test_a():\n    assert a() == 1\n"
            ),
        }
    )
    src = pkg / "tests/unit/test_a.py"
    tgt = pkg / "tests/integration/test_a.py"

    warnings = execute_relocate(_op("relocate", src, tgt), pkg)

    assert warnings == []
    assert not src.exists()
    assert tgt.exists()
    assert "def test_a():" in tgt.read_text()


def test_execute_relocate_reroutes_when_target_exists(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """RELOCATE re-routes through _safe_move_units when the target pre-exists.

    The source's unit must land in the existing target file (not overwrite
    it), the existing test must survive, and the source must be deleted.
    """
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/unit/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/unit/test_a.py": "def test_from_unit():\n    assert True\n",
            "tests/integration/test_a.py": "def test_existing():\n    assert True\n",
        }
    )
    src = pkg / "tests/unit/test_a.py"
    tgt = pkg / "tests/integration/test_a.py"

    warnings = execute_relocate(_op("relocate", src, tgt), pkg)

    assert warnings == [
        "relocate: target test_a.py already exists; "
        "re-routing test_a.py through _safe_move_units"
    ]
    assert not src.exists()
    body = tgt.read_text()
    assert "def test_existing():" in body
    assert "def test_from_unit():" in body


def test_execute_relocate_patches_dunder_depth_and_cross_imports(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """RELOCATE patches ``parents[N]`` for the depth delta on a nested move.

    Moving ``tests/integration/hooks/test_h.py`` (depth 4) up to
    ``tests/integration/test_h.py`` (depth 3) shifts the file one level
    closer to the project root, so ``Path(__file__).parents[3]`` must be
    re-pointed to ``parents[2]`` to keep resolving to the same ancestor.
    """
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/hooks/__init__.py": "",
            "tests/integration/hooks/test_h.py": (
                "from pathlib import Path\n"
                "ROOT = Path(__file__).parents[3]\n\n"
                "def test_h():\n    assert ROOT.name == 'pkg'\n"
            ),
        }
    )
    src = pkg / "tests/integration/hooks/test_h.py"
    tgt = pkg / "tests/integration/test_h.py"

    warnings = execute_relocate(_op("relocate", src, tgt), pkg)

    assert any(
        "file-depth-drift" in w and "parents[3] -> parents[2]" in w for w in warnings
    )
    assert "Path(__file__).parents[2]" in tgt.read_text()
    assert not src.exists()


def test_execute_relocate_rewrites_cross_test_imports(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """RELOCATE rewrites sibling imports of the moved module's dotted path."""
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/e2e/__init__.py": "",
            "tests/integration/test_a.py": (
                "def helper():\n    return 1\n\n"
                "def test_a():\n    assert helper() == 1\n"
            ),
            "tests/e2e/test_importer.py": (
                "from tests.integration.test_a import helper\n\n"
                "def test_x():\n    assert helper() == 1\n"
            ),
        }
    )
    src = pkg / "tests/integration/test_a.py"
    tgt = pkg / "tests/e2e/test_a.py"

    warnings = execute_relocate(_op("relocate", src, tgt), pkg)

    assert any("rewrote import in tests/e2e/test_importer.py" in w for w in warnings)
    importer_body = (pkg / "tests/e2e/test_importer.py").read_text()
    assert "from tests.e2e.test_a import helper" in importer_body
