"""Split from ``test_extract_calls__extract_module_info.py``."""

from pathlib import Path

import pytest

from axm_ast.core.parser import extract_module_info


class TestExtractImportsRelative:
    """Public-API drivers for ``from ... import ...`` parsing.

    These scenarios were previously asserted directly against the
    private ``axm_ast.core.flows._parse_import_from_node`` helper.
    They are now expressed against the public ``extract_module_info``
    output (``ModuleInfo.imports``), which is the same data the
    private helper feeds into the cross-module resolver.
    """

    @pytest.mark.parametrize(
        ("source", "expected_module", "expected_names"),
        [
            pytest.param(
                "from .response import HttpResponse\n",
                "response",
                {"HttpResponse"},
                id="single",
            ),
            pytest.param(
                "from .models import A, B\n",
                "models",
                {"A", "B"},
                id="multi",
            ),
        ],
    )
    def test_relative_import(
        self,
        tmp_path: Path,
        source: str,
        expected_module: str,
        expected_names: set[str],
    ) -> None:
        """``from .pkg import ...`` → level=1 relative import with names."""
        f = tmp_path / "mod.py"
        f.write_text(source)
        mod = extract_module_info(f)
        rels = [i for i in mod.imports if i.is_relative]
        assert len(rels) == 1
        assert rels[0].module == expected_module
        assert rels[0].level == 1
        assert set(rels[0].names) == expected_names
