"""Split from ``test_nodes.py``."""

from axm_ast.models.nodes import ImportInfo


class TestImportInfo:
    """Tests for ImportInfo model."""

    def test_absolute_import(self) -> None:
        imp = ImportInfo(module="pathlib", names=["Path"])
        assert imp.is_relative is False
        assert imp.level == 0

    def test_relative_import(self) -> None:
        imp = ImportInfo(module="utils", names=["helper"], is_relative=True, level=1)
        assert imp.is_relative is True
        assert imp.level == 1


class TestImportInfoFromModels:
    """Tests for ImportInfo model."""

    def test_import_with_alias(self):
        imp = ImportInfo(module="numpy", names=["numpy"], alias="np")
        assert imp.alias == "np"

    def test_star_import(self):
        imp = ImportInfo(module="os", names=["*"])
        assert "*" in imp.names
