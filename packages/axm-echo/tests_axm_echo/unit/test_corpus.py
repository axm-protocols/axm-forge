"""Unit tests for axm_echo.corpus pure logic (the Symbol projection).

Only the I/O-free surface is exercised here: the ``Symbol`` dataclass and
its derived properties (``embed_text``, ``has_doc``, ``as_dict``). The
filesystem extractors (``extract_package``, ``discover_package_roots``,
``extract_monorepo``) read the real tree and are covered under
``tests/integration/`` -- not duplicated here.
"""

from __future__ import annotations

from axm_echo.corpus import Symbol


def _symbol(*, doc_full: str = "", body_norm: str = "") -> Symbol:
    """Build a Symbol with sane defaults; vary only the embed inputs."""
    return Symbol(
        qualname="pkg.mod.fn",
        name="fn",
        package="pkg",
        workspace="ws",
        kind="function",
        signature="def fn(x: int) -> int",
        doc_first_line=doc_full.splitlines()[0] if doc_full else "",
        doc_full=doc_full,
        body_norm=body_norm,
        path="/abs/pkg/mod.py",
        line=10,
    )


def test_embed_text_uses_docstring_when_present() -> None:
    """AC3: a documented symbol embeds its signature + docstring."""
    sym = _symbol(doc_full="Compute the answer.", body_norm="return 42")

    text = sym.embed_text

    assert "def fn(x: int) -> int" in text
    assert "Compute the answer." in text
    # The code body is NOT used once a docstring exists.
    assert "return 42" not in text


def test_embed_text_falls_back_to_code_when_undocumented() -> None:
    """AC3: an undocumented symbol embeds its signature + normalized code."""
    sym = _symbol(doc_full="   ", body_norm="def fn(x: int) -> int")

    text = sym.embed_text

    assert text.startswith("def fn(x: int) -> int")
    # Whitespace-only docstring is treated as absent.
    assert sym.has_doc is False


def test_has_doc_reflects_docstring_presence() -> None:
    """has_doc is True only for a non-blank docstring."""
    assert _symbol(doc_full="A real summary.").has_doc is True
    assert _symbol(doc_full="").has_doc is False
    assert _symbol(doc_full="\n  \t ").has_doc is False


def test_as_dict_is_flat_and_carries_derived_fields() -> None:
    """as_dict projects every field plus the derived embed_text/has_doc."""
    sym = _symbol(doc_full="Doc here.")

    flat = sym.as_dict()

    assert flat["qualname"] == "pkg.mod.fn"
    assert flat["package"] == "pkg"
    assert flat["kind"] == "function"
    assert flat["line"] == 10
    assert flat["has_doc"] is True
    assert flat["embed_text"] == sym.embed_text
    # The mapping is flat (string-keyed, JSON-friendly).
    assert set(flat) == {
        "qualname",
        "name",
        "package",
        "workspace",
        "kind",
        "signature",
        "doc_first_line",
        "doc_full",
        "body_norm",
        "embed_text",
        "has_doc",
        "path",
        "line",
    }
