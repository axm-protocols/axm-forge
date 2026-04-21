from __future__ import annotations

from pathlib import Path

from axm_ast.core.doc_impact import _extract_doc_signatures


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
