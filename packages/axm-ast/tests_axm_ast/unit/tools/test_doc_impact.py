"""Unit tests for the agent-facing description of ``DocImpactTool``.

Mirrors ``src/axm_ast/tools/doc_impact.py`` 1:1. The description attribute is
the only text MCP discovery and the ``axm`` help command ever show, so the
honest lexical caveat must live there, not only in the core docstring.
"""

from __future__ import annotations

from axm_ast.tools.doc_impact import DocImpactTool


def _served_description() -> str:
    """Return the lowercased description served by MCP discovery / CLI help."""
    description = getattr(DocImpactTool, "description", None)
    if not isinstance(description, str) or not description.strip():
        description = DocImpactTool.__doc__ or ""
    return description.lower()


def test_description_states_matching_is_lexical() -> None:
    """AC1: the served description says the matching is lexical, on backticks."""
    text = _served_description()

    assert "lexical" in text
    assert "backtick" in text


def test_description_frames_result_as_pages_to_read() -> None:
    """AC2: the served description frames the output as pages to read, not a proof."""
    text = _served_description()

    assert "pages to read" in text
    assert "not a proof" in text


def test_description_warns_about_name_drop_suppression() -> None:
    """AC3: the served description warns a name-drop clears the undocumented list."""
    text = _served_description()

    assert "name-drop" in text
    assert "undocumented" in text
