"""Split from ``test_extract_calls__extract_module_info.py``."""

from pathlib import Path

from axm_ast.core.parser import extract_module_info


class TestExtractImportsRelative:
    """Public-API drivers for ``from ... import ...`` parsing.

    These scenarios were previously asserted directly against the
    private ``axm_ast.core.flows._parse_import_from_node`` helper.
    They are now expressed against the public ``extract_module_info``
    output (``ModuleInfo.imports``), which is the same data the
    private helper feeds into the cross-module resolver.
    """

    def test_single_relative_import(self, tmp_path: Path) -> None:
        """``from .response import X`` → module='response', names=['X']."""
        f = tmp_path / "mod.py"
        f.write_text("from .response import HttpResponse\n")
        mod = extract_module_info(f)
        rels = [i for i in mod.imports if i.is_relative]
        assert len(rels) == 1
        assert rels[0].module == "response"
        assert rels[0].level == 1
        assert rels[0].names == ["HttpResponse"]

    def test_multi_relative_import(self, tmp_path: Path) -> None:
        """``from .models import A, B`` → module='.models' / names=['A','B']."""
        f = tmp_path / "mod.py"
        f.write_text("from .models import A, B\n")
        mod = extract_module_info(f)
        rels = [i for i in mod.imports if i.is_relative]
        assert len(rels) == 1
        assert rels[0].module == "models"
        assert rels[0].level == 1
        assert set(rels[0].names) == {"A", "B"}
