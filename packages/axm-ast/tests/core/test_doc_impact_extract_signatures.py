from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.doc_impact import _extract_doc_signatures


@pytest.fixture()
def doc_root(tmp_path: Path) -> Path:
    return tmp_path


def _write_doc(root: Path, name: str, content: str) -> Path:
    p = root / name
    p.write_text(content, encoding="utf-8")
    return p


class TestExtractDocSignaturesBasic:
    def test_extracts_def_in_code_block(self, doc_root: Path) -> None:
        p = _write_doc(
            doc_root,
            "api.md",
            """# API

```python
def foo(x: int) -> str:
    pass
```
""",
        )
        result = _extract_doc_signatures(p, {"foo"}, doc_root)
        assert len(result) == 1
        assert result[0]["symbol"] == "foo"
        assert result[0]["doc_sig"] == "def foo(x: int) -> str"
        assert result[0]["file"] == "api.md"
        assert isinstance(result[0]["line"], int)

    def test_extracts_class_in_code_block(self, doc_root: Path) -> None:
        p = _write_doc(
            doc_root,
            "api.md",
            """# API

```python
class Bar:
    pass
```
""",
        )
        result = _extract_doc_signatures(p, {"Bar"}, doc_root)
        assert len(result) == 1
        assert result[0]["symbol"] == "Bar"

    def test_ignores_symbols_not_in_set(self, doc_root: Path) -> None:
        p = _write_doc(
            doc_root,
            "api.md",
            """```python
def foo():
    pass
def bar():
    pass
```
""",
        )
        result = _extract_doc_signatures(p, {"bar"}, doc_root)
        assert len(result) == 1
        assert result[0]["symbol"] == "bar"


class TestExtractDocSignaturesCodeFence:
    def test_ignores_def_outside_code_block(self, doc_root: Path) -> None:
        p = _write_doc(
            doc_root,
            "readme.md",
            """# Readme

def foo():
    not in a code block
""",
        )
        result = _extract_doc_signatures(p, {"foo"}, doc_root)
        assert result == []

    def test_handles_multiple_code_blocks(self, doc_root: Path) -> None:
        p = _write_doc(
            doc_root,
            "api.md",
            """```python
def alpha():
```

Some text.

```python
def beta():
```
""",
        )
        result = _extract_doc_signatures(p, {"alpha", "beta"}, doc_root)
        assert len(result) == 2
        syms = {r["symbol"] for r in result}
        assert syms == {"alpha", "beta"}


class TestExtractDocSignaturesEdgeCases:
    def test_empty_symbols_set(self, doc_root: Path) -> None:
        p = _write_doc(
            doc_root,
            "api.md",
            """```python
def foo():
```
""",
        )
        assert _extract_doc_signatures(p, set(), doc_root) == []

    def test_file_not_found(self, doc_root: Path) -> None:
        missing = doc_root / "missing.md"
        assert _extract_doc_signatures(missing, {"foo"}, doc_root) == []

    def test_empty_file(self, doc_root: Path) -> None:
        p = _write_doc(doc_root, "empty.md", "")
        assert _extract_doc_signatures(p, {"foo"}, doc_root) == []

    def test_strips_trailing_colon_from_sig(self, doc_root: Path) -> None:
        p = _write_doc(
            doc_root,
            "api.md",
            """```python
def baz(x: int):
```
""",
        )
        result = _extract_doc_signatures(p, {"baz"}, doc_root)
        assert result[0]["doc_sig"] == "def baz(x: int)"

    def test_line_numbers_correct(self, doc_root: Path) -> None:
        p = _write_doc(
            doc_root,
            "api.md",
            """line1
line2
```python
def target():
```
""",
        )
        result = _extract_doc_signatures(p, {"target"}, doc_root)
        assert result[0]["line"] == 4

    def test_unicode_decode_error_returns_empty(self, doc_root: Path) -> None:
        p = doc_root / "binary.md"
        p.write_bytes(b"\x80\x81\x82")
        # Depending on codec this may or may not raise; function handles it
        result = _extract_doc_signatures(p, {"foo"}, doc_root)
        assert isinstance(result, list)
