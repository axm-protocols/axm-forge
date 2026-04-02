from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.doc_impact import _extract_doc_signatures, _match_signature_line


@pytest.fixture()
def doc_root(tmp_path: Path) -> Path:
    return tmp_path / "docs"


class TestMatchSignatureLine:
    """Unit tests for _match_signature_line helper."""

    def test_matches_def(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        result = _match_signature_line(
            "def my_func(x):", 5, {"my_func"}, path, tmp_path
        )
        assert result is not None
        assert result["symbol"] == "my_func"

    def test_matches_class(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        result = _match_signature_line(
            "class MyClass:", 10, {"MyClass"}, path, tmp_path
        )
        assert result is not None
        assert result["symbol"] == "MyClass"

    def test_no_match_unknown_symbol(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        result = _match_signature_line(
            "def other_func():", 5, {"my_func"}, path, tmp_path
        )
        assert result is None

    def test_no_match_plain_text(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        result = _match_signature_line(
            "some plain text", 5, {"my_func"}, path, tmp_path
        )
        assert result is None


class TestExtractDocSignatures:
    """Regression tests for _extract_doc_signatures."""

    def test_extracts_from_code_block(self, tmp_path: Path) -> None:
        doc = tmp_path / "api.md"
        doc.write_text(
            "# API\n\n```python\ndef my_func(x):\n    pass\n```\n", encoding="utf-8"
        )
        results = _extract_doc_signatures(doc, {"my_func"}, tmp_path)
        assert len(results) == 1
        assert results[0]["symbol"] == "my_func"

    def test_ignores_outside_code_block(self, tmp_path: Path) -> None:
        doc = tmp_path / "api.md"
        doc.write_text("def my_func(x):\n    pass\n", encoding="utf-8")
        results = _extract_doc_signatures(doc, {"my_func"}, tmp_path)
        assert results == []

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        doc = tmp_path / "missing.md"
        results = _extract_doc_signatures(doc, {"my_func"}, tmp_path)
        assert results == []

    def test_multiple_symbols(self, tmp_path: Path) -> None:
        doc = tmp_path / "api.md"
        doc.write_text(
            "```python\ndef func_a():\n    pass\nclass ClassB:\n    pass\n```\n",
            encoding="utf-8",
        )
        results = _extract_doc_signatures(doc, {"func_a", "ClassB"}, tmp_path)
        names = {r["symbol"] for r in results}
        assert "func_a" in names
        assert "ClassB" in names

    def test_empty_symbols_set(self, tmp_path: Path) -> None:
        doc = tmp_path / "api.md"
        doc.write_text("```python\ndef my_func():\n    pass\n```\n", encoding="utf-8")
        results = _extract_doc_signatures(doc, set(), tmp_path)
        assert results == []

    def test_multiple_code_blocks(self, tmp_path: Path) -> None:
        doc = tmp_path / "api.md"
        doc.write_text(
            "```python\ndef a():\n    pass\n```\n\ntext\n\n"
            "```python\ndef b():\n    pass\n```\n",
            encoding="utf-8",
        )
        results = _extract_doc_signatures(doc, {"a", "b"}, tmp_path)
        assert len(results) == 2
