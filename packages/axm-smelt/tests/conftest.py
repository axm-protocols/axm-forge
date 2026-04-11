"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_json() -> str:
    return '{\n  "name": "Alice",\n  "age": 30\n}'


@pytest.fixture
def sample_json_array() -> str:
    return '[{"a": 1}, {"b": 2}]'


@pytest.fixture
def sample_json_minified() -> str:
    return '{"a":1}'


@pytest.fixture
def sample_yaml() -> str:
    return "key: value\nlist:\n  - item"


@pytest.fixture
def sample_markdown() -> str:
    return (
        "# Project Title\n"
        "\n"
        "## Overview\n"
        "\n"
        "Some description text.\n"
        "\n"
        "| Column A | Column B |\n"
        "|----------|----------|\n"
        "| value1   | value2   |\n"
        "\n"
        "```python\n"
        "print('hello')\n"
        "```\n"
        "\n"
        "See [docs](https://example.com) for details.\n"
    )


@pytest.fixture
def sample_markdown_table() -> str:
    return "| Name | Age |\n|------|-----|\n| Alice | 30 |\n| Bob   | 25 |\n"


@pytest.fixture
def sample_xml() -> str:
    return "<root><a>1</a></root>"


@pytest.fixture
def sample_plain_text() -> str:
    return "hello world"
