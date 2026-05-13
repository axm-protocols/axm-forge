from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from axm_ast.core.analyzer import module_dotted_name
from axm_ast.tools.search import SearchTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_func(name: str, kind: str = "function") -> SimpleNamespace:
    return SimpleNamespace(name=name, kind=kind)


def _make_class(
    name: str, methods: list[SimpleNamespace] | None = None
) -> SimpleNamespace:
    return SimpleNamespace(name=name, methods=methods or [])


def _make_mod(
    *,
    path: Path,
    name: str | None = None,
    functions: list[SimpleNamespace] | None = None,
    classes: list[SimpleNamespace] | None = None,
    variables: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        path=path,
        name=name,
        functions=functions or [],
        classes=classes or [],
        variables=variables or [],
    )


def _make_pkg(
    root: Path,
    modules: list[SimpleNamespace],
) -> SimpleNamespace:
    return SimpleNamespace(root=root, modules=modules)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_suggestion_module_populated(tmp_path: Path) -> None:
    """Suggestions must have a non-None module even when mod.name is None."""
    root = tmp_path / "src" / "mypkg"
    root.mkdir(parents=True)
    mod_path = root / "helpers.py"
    mod_path.touch()

    mod = _make_mod(
        path=mod_path,
        name=None,
        functions=[_make_func("compute_score")],
    )
    pkg = _make_pkg(root=root, modules=[mod])

    # Query with a typo so fuzzy matching kicks in
    suggestions = SearchTool._find_suggestions(pkg, "compute_scor")

    assert len(suggestions) >= 1
    for s in suggestions:
        assert s["module"] is not None, "suggestion module must not be None"


def test_suggestion_module_is_dotted(tmp_path: Path) -> None:
    """Suggestion module must match module_dotted_name(mod.path, pkg.root)."""
    root = tmp_path / "src" / "mypkg"
    sub = root / "core"
    sub.mkdir(parents=True)
    mod_path = sub / "analyzer.py"
    mod_path.touch()

    expected_dotted = module_dotted_name(mod_path, root)

    mod = _make_mod(
        path=mod_path,
        name=None,
        functions=[_make_func("analyze_data")],
    )
    pkg = _make_pkg(root=root, modules=[mod])

    suggestions = SearchTool._find_suggestions(pkg, "analyze_dat")

    assert len(suggestions) >= 1
    assert suggestions[0]["module"] == expected_dotted


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_suggestion_module_uses_mod_name_when_set(tmp_path: Path) -> None:
    """When mod.name is already set, it is used directly (no fallback)."""
    root = tmp_path / "src" / "mypkg"
    root.mkdir(parents=True)
    mod_path = root / "utils.py"
    mod_path.touch()

    explicit_name = "mypkg.utils"
    mod = _make_mod(
        path=mod_path,
        name=explicit_name,
        functions=[_make_func("do_stuff")],
    )
    pkg = _make_pkg(root=root, modules=[mod])

    suggestions = SearchTool._find_suggestions(pkg, "do_stuf")

    assert len(suggestions) >= 1
    assert suggestions[0]["module"] == explicit_name


def test_suggestion_empty_package(tmp_path: Path) -> None:
    """Package with no modules returns empty suggestions without crashing."""
    pkg = _make_pkg(root=tmp_path, modules=[])

    suggestions = SearchTool._find_suggestions(pkg, "anything")

    assert suggestions == []
