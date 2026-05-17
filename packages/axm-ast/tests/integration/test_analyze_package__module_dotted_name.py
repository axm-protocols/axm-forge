"""Split from ``test_src_layout_2.py``."""

from pathlib import Path

import pytest

from axm_ast import analyze_package
from axm_ast.core.analyzer import module_dotted_name


@pytest.mark.functional
def test_callers_no_src_prefix(tmp_path: Path) -> None:
    """Callers in src-layout packages have clean module names."""
    pkg_dir = tmp_path / "src" / "mypkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "core.py").write_text("def greet():\n    return 'hi'\n")
    (pkg_dir / "cli.py").write_text(
        "from mypkg.core import greet\n\ndef main():\n    greet()\n"
    )

    pkg = analyze_package(tmp_path)
    for mod in pkg.modules:
        name = module_dotted_name(mod.path, pkg.root)
        assert not name.startswith("src."), (
            f"Module '{name}' has src. prefix — not a valid import path"
        )


@pytest.mark.functional
def test_describe_no_src_prefix(tmp_path: Path) -> None:
    """Describe output for src-layout packages uses importable module names."""
    pkg_dir = tmp_path / "src" / "mypkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "utils.py").write_text("def helper():\n    pass\n")
    (pkg_dir / "sub" / "__init__.py").parent.mkdir()
    (pkg_dir / "sub" / "__init__.py").write_text("")
    (pkg_dir / "sub" / "deep.py").write_text("X = 1\n")

    pkg = analyze_package(tmp_path)
    for mod in pkg.modules:
        name = module_dotted_name(mod.path, pkg.root)
        assert not name.startswith("src."), f"Module name '{name}' is not importable"
        assert all(part.isidentifier() for part in name.split(".")), (
            f"Module name '{name}' is not a valid dotted import path"
        )


@pytest.mark.functional
def test_no_init_in_src_subdir(tmp_path: Path) -> None:
    """Handles src/scripts/util.py gracefully when scripts has no __init__.py."""
    scripts_dir = tmp_path / "src" / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "util.py").write_text("x = 1\n")

    pkg = analyze_package(tmp_path)
    for mod in pkg.modules:
        name = module_dotted_name(mod.path, pkg.root)
        assert not name.startswith("src."), f"Module '{name}' has src. prefix"
