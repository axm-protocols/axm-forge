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


class TestExtractAllExports:
    """``__all__`` parsing across list, tuple and non-literal styles."""

    @pytest.mark.parametrize(
        ("rhs", "expected"),
        [
            pytest.param('["foo", "bar"]', ["foo", "bar"], id="list"),
            pytest.param('("foo", "bar")', ["foo", "bar"], id="tuple"),
            pytest.param('("solo",)', ["solo"], id="single-tuple"),
        ],
    )
    def test_all_exports_sequence_literal(
        self, tmp_path: Path, rhs: str, expected: list[str]
    ) -> None:
        """Both list and RUF022-style tuple ``__all__`` are parsed."""
        f = tmp_path / "mod.py"
        f.write_text(
            f"__all__ = {rhs}\ndef foo() -> None: ...\ndef bar() -> None: ...\n"
        )
        mod = extract_module_info(f)
        assert mod.all_exports == expected

    def test_tuple_all_exports_drives_public_functions(self, tmp_path: Path) -> None:
        """Tuple ``__all__`` must gate ``public_functions`` (not blank it)."""
        f = tmp_path / "mod.py"
        f.write_text(
            '__all__ = ("foo",)\ndef foo() -> None: ...\ndef bar() -> None: ...\n'
        )
        mod = extract_module_info(f)
        assert [fn.name for fn in mod.public_functions] == ["foo"]

    def test_non_literal_all_exports_is_none(self, tmp_path: Path) -> None:
        """A non-parsable ``__all__`` yields None (unknown), not [] (empty)."""
        f = tmp_path / "mod.py"
        f.write_text("import other\n__all__ = other.__all__\ndef foo() -> None: ...\n")
        mod = extract_module_info(f)
        assert mod.all_exports is None


class TestRawDocstring:
    """Raw / prefixed docstrings are de-quoted without leaking the prefix."""

    def test_raw_module_docstring_prefix_stripped(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text('r"""\\alpha raw doc."""\n')
        mod = extract_module_info(f)
        assert mod.docstring == "\\alpha raw doc."
