"""Split from ``test_search_suggestion.py``."""

from pathlib import Path
from types import SimpleNamespace

from axm_ast.core.analyzer import module_dotted_name
from axm_ast.tools.search import SearchTool
from tests.integration._helpers import _make_func, _make_mod


def _make_pkg(
    root: Path,
    modules: list[SimpleNamespace],
) -> SimpleNamespace:
    return SimpleNamespace(root=root, modules=modules)


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

    suggestions = SearchTool.find_suggestions(pkg, "analyze_dat")

    assert len(suggestions) >= 1
    assert suggestions[0]["module"] == expected_dotted
