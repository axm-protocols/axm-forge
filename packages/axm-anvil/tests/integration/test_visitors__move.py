"""AC3: a moved block whose local/kwarg shadows a top-level helper must not
pull that helper into the target (nor orphan it out of the source)."""

from pathlib import Path

import libcst as cst

from axm_anvil._cst.visitors import ReferenceCollector
from axm_anvil.core.move import move_symbols


def _write_pyproject(root: Path, name: str = "mypkg") -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
    )


def _setup_shadow_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    _write_pyproject(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    a = pkg / "a.py"
    # ``y`` is an unrelated top-level helper; ``moved`` only ever refers to its
    # own parameter ``y``, so ``y`` is NOT a dependency of the moved block.
    a.write_text("def y():\n    return 99\n\ndef moved(y):\n    return y + 1\n")
    b = pkg / "b.py"
    b.write_text("def keep():\n    return 0\n")
    return tmp_path, a, b


def test_reference_collector_ignores_shadowing_local() -> None:
    """The collector treats the shadowing param ``y`` as bound, not a ref."""
    block = cst.parse_module("def moved(y):\n    return y + 1\n")
    collector = ReferenceCollector()
    block.visit(collector)
    assert "y" not in collector.names


def test_homonym_helper_not_embedded_nor_orphaned(tmp_path: Path) -> None:
    root, a, b = _setup_shadow_fixture(tmp_path)

    move_symbols(a, b, ["moved"], workspace_root=root)

    source_after = a.read_text()
    target_after = b.read_text()
    # The unrelated top-level helper stays in the source module...
    assert "def y(" in source_after
    # ...and is never copied into the target.
    assert "def y(" not in target_after
    assert "def moved(" in target_after
