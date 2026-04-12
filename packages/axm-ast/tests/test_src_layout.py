from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package, module_dotted_name

# ── Helpers ─────────────────────────────────────────────────────────


def _make_src_layout(root: Path, pkg_name: str = "mypkg") -> Path:
    """Create a minimal src-layout package and return the project root."""
    pkg_dir = root / "src" / pkg_name
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "core.py").write_text("def greet():\n    return 'hi'\n")
    return root


# ── Unit tests ──────────────────────────────────────────────────────


def test_module_dotted_name_src_layout():
    """module_dotted_name strips src/ prefix for src-layout packages."""
    mod_path = Path("/tmp/pkg/src/mypkg/core.py")
    root = Path("/tmp/pkg")
    result = module_dotted_name(mod_path, root)
    assert result == "mypkg.core"


def test_module_dotted_name_flat_layout():
    """module_dotted_name works unchanged for flat-layout packages."""
    mod_path = Path("/tmp/pkg/mypkg/core.py")
    root = Path("/tmp/pkg")
    result = module_dotted_name(mod_path, root)
    assert result == "mypkg.core"


def test_module_dotted_name_init():
    """module_dotted_name strips __init__ and src/ for init files."""
    mod_path = Path("/tmp/pkg/src/mypkg/__init__.py")
    root = Path("/tmp/pkg")
    result = module_dotted_name(mod_path, root)
    assert result == "mypkg"


def test_analyze_package_src_layout_root(tmp_path: Path) -> None:
    """analyze_package sets root inside src/ for src-layout packages."""
    _make_src_layout(tmp_path)

    pkg = analyze_package(tmp_path)
    # root should point inside src/, not project root
    assert pkg.root != tmp_path, "root should not be the project directory"
    assert tmp_path / "src" == pkg.root or pkg.root.is_relative_to(tmp_path / "src"), (
        f"root {pkg.root} should be inside src/"
    )


# ── Functional tests ────────────────────────────────────────────────


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


# ── Edge cases ──────────────────────────────────────────────────────


def test_package_named_src():
    """A package literally named 'src' keeps its name."""
    mod_path = Path("/tmp/pkg/src/src/__init__.py")
    root = Path("/tmp/pkg")
    result = module_dotted_name(mod_path, root)
    assert result == "src", f"Expected 'src', got '{result}'"


def test_nested_src_dirs():
    """Only top-level src/ is stripped, not nested ones."""
    mod_path = Path("/tmp/pkg/src/mypkg/src/inner.py")
    root = Path("/tmp/pkg")
    result = module_dotted_name(mod_path, root)
    assert result == "mypkg.src.inner", f"Expected 'mypkg.src.inner', got '{result}'"


def test_no_init_in_src_subdir(tmp_path: Path) -> None:
    """Handles src/scripts/util.py gracefully when scripts has no __init__.py."""
    scripts_dir = tmp_path / "src" / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "util.py").write_text("x = 1\n")

    # Should not crash
    pkg = analyze_package(tmp_path)
    for mod in pkg.modules:
        name = module_dotted_name(mod.path, pkg.root)
        assert not name.startswith("src."), f"Module '{name}' has src. prefix"
