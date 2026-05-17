from __future__ import annotations

import pytest

from axm_smelt.core.detector import (
    detect_format,
    detect_format_parsed,
    try_json,
    try_markdown,
    try_xml,
    try_yaml,
)
from axm_smelt.core.models import Format


def test_detect_json() -> None:
    assert detect_format('{"a": 1}') == Format.JSON


def test_detect_yaml(sample_yaml: str) -> None:
    assert detect_format(sample_yaml) == Format.YAML


# --- Unit tests: try_markdown ---


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("# Heading 1\n\n## Heading 2\n\nSome content.", id="headings"),
        pytest.param(
            "| Col A | Col B |\n|-------|-------|\n| x     | y     |", id="table"
        ),
        pytest.param("# Title\n\n```python\nprint('hi')\n```", id="fenced_code"),
        pytest.param(
            "# Title\n\nSee [link](https://example.com) for info.", id="links"
        ),
    ],
)
def test_try_markdown_positive_indicators(text: str) -> None:
    assert try_markdown(text) == Format.MARKDOWN


def test_try_markdown_single_indicator() -> None:
    text = "# Just a heading\n\nPlain text below."
    assert try_markdown(text) is None


# --- Functional tests ---


def test_detect_markdown_full(sample_markdown: str) -> None:
    assert detect_format(sample_markdown) == Format.MARKDOWN


def test_detect_markdown_parsed(sample_markdown: str) -> None:
    fmt, data = detect_format_parsed(sample_markdown)
    assert fmt == Format.MARKDOWN
    assert data is None


# --- Edge cases ---


def test_yaml_with_comments() -> None:
    text = "# comment\nkey: value"
    assert detect_format(text) == Format.YAML


def test_json_with_markdown_values() -> None:
    text = '{"body": "# heading"}'
    assert detect_format(text) == Format.JSON


def test_single_heading_only() -> None:
    text = "# Title\nSome plain text"
    assert detect_format(text) == Format.TEXT


def test_empty_fenced_block() -> None:
    text = "```\n```"
    assert detect_format(text) == Format.TEXT


def test_html_heavy_markdown() -> None:
    text = "<div># heading</div>"
    assert detect_format(text) == Format.TEXT


def test_detect_xml(sample_xml: str) -> None:
    assert detect_format(sample_xml) == Format.XML


def test_detect_plain_text(sample_plain_text: str) -> None:
    assert detect_format(sample_plain_text) == Format.TEXT


def test_detect_json_array() -> None:
    assert detect_format('[{"a":1},{"a":2}]') == Format.JSON


# --- Unit tests: try_json ---


def test_try_json_valid() -> None:
    assert try_json('{"a": 1}') == Format.JSON


def test_try_json_invalid() -> None:
    assert try_json("not json") is None


# --- Unit tests: try_xml ---


def test_try_xml_valid() -> None:
    assert try_xml("<root>x</root>") == Format.XML


def test_try_xml_comment() -> None:
    assert try_xml("<!-- comment -->") is None


# --- Unit tests: try_yaml ---


def test_try_yaml_valid() -> None:
    assert try_yaml("key: value") == Format.YAML


def test_try_yaml_plain_string() -> None:
    assert try_yaml("hello world") is None


# --- Edge cases ---


def test_edge_empty_string() -> None:
    assert detect_format("") == Format.TEXT


def test_edge_whitespace_only() -> None:
    assert detect_format("   ") == Format.TEXT


def test_edge_json_array() -> None:
    assert detect_format("[1,2,3]") == Format.JSON


def test_edge_malformed_json_brace() -> None:
    result = detect_format("{bad")
    assert result in (Format.YAML, Format.TEXT)


def test_edge_xml_doctype() -> None:
    assert detect_format("<!DOCTYPE html>") != Format.XML
