"""Split from ``test_analyzer.py``."""

from pathlib import Path

from axm_ast.core.analyzer import module_dotted_name


class TestModuleDottedName:
    def test_src_layout(self) -> None:
        result = module_dotted_name(
            Path("/tmp/pkg/src/mypkg/core.py"), Path("/tmp/pkg")
        )
        assert result == "mypkg.core"

    def test_flat_layout(self) -> None:
        result = module_dotted_name(Path("/tmp/pkg/mypkg/core.py"), Path("/tmp/pkg"))
        assert result == "mypkg.core"

    def test_init_file(self) -> None:
        result = module_dotted_name(
            Path("/tmp/pkg/src/mypkg/__init__.py"), Path("/tmp/pkg")
        )
        assert result == "mypkg"

    def test_package_named_src(self) -> None:
        result = module_dotted_name(
            Path("/tmp/pkg/src/src/__init__.py"), Path("/tmp/pkg")
        )
        assert result == "src"

    def test_nested_src_dirs(self) -> None:
        result = module_dotted_name(
            Path("/tmp/pkg/src/mypkg/src/inner.py"), Path("/tmp/pkg")
        )
        assert result == "mypkg.src.inner"
