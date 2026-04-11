from __future__ import annotations

import yaml

from axm_smelt.core.models import SmeltContext
from axm_smelt.core.pipeline import check, smelt
from axm_smelt.strategies.minify import MinifyStrategy

# === JSON (existing, unchanged) ===


def test_minify_json() -> None:
    text = '{\n  "a": 1,\n  "b": 2\n}'
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert result == '{"a":1,"b":2}'


def test_minify_json_array() -> None:
    text = '[{"a": 1}, {"b": 2}]'
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert result == '[{"a":1},{"b":2}]'


def test_minify_non_json() -> None:
    text = "plain text"
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert result == text


# === YAML unit tests ===


def test_minify_yaml_basic() -> None:
    text = "key: value\nlist:\n  - item1\n  - item2"
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert len(result) <= len(text)
    parsed = yaml.safe_load(result)
    assert parsed == {"key": "value", "list": ["item1", "item2"]}


def test_minify_yaml_irregular_ws() -> None:
    text = "key:   value  \n\n\nlist:\n    - item1\n    - item2  \n"
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    # Trailing spaces, blank lines, 4-space indent should be normalized
    assert "   " not in result
    assert "\n\n" not in result
    parsed = yaml.safe_load(result)
    assert parsed == {"key": "value", "list": ["item1", "item2"]}


def test_minify_yaml_preserves_data() -> None:
    text = "name: test\nitems:\n  - a\n  - b\nnested:\n  x: 1\n  y: 2"
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert yaml.safe_load(result) == yaml.safe_load(text)


# === XML unit tests ===


def test_minify_xml_basic() -> None:
    text = "<root>\n  <item>value</item>\n</root>"
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert result == "<root><item>value</item></root>"


def test_minify_xml_preserves_text() -> None:
    text = "<tag>  text content  </tag>"
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert "text content" in result


def test_minify_xml_attributes() -> None:
    text = '<item name="test" id="1">val</item>'
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert 'name="test"' in result
    assert 'id="1"' in result
    assert "val" in result


# === JSON unchanged (regression) ===


def test_minify_json_unchanged() -> None:
    """Existing JSON minification behavior is unchanged."""
    text = '{"key": "value",  "num": 42}'
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert result == '{"key":"value","num":42}'


# === Functional tests ===


def test_smelt_yaml_savings() -> None:
    yaml_text = (
        "name: test\nitems:\n  - item1\n  - item2\n  - item3\nmetadata:\n  version: 1"
    )
    report = smelt(yaml_text, strategies=["minify"])
    assert report.savings_pct > 0


def test_smelt_xml_savings() -> None:
    xml_text = "<root>\n  <item>value1</item>\n  <item>value2</item>\n</root>"
    report = smelt(xml_text, strategies=["minify"])
    assert report.savings_pct > 0


def test_check_yaml_estimates() -> None:
    yaml_text = "name: test\nitems:\n  - a\n  - b\nconfig:\n  debug: true"
    report = check(yaml_text)
    assert "minify" in report.strategy_estimates
    assert report.strategy_estimates["minify"] > 0


# === Edge cases ===


def test_minify_yaml_anchors() -> None:
    text = (
        "defaults: &defaults\n  color: red\n  size: large\n"
        "item:\n  <<: *defaults\n  name: widget"
    )
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    # Should either handle correctly or fall back unchanged
    parsed = yaml.safe_load(text)
    result_parsed = yaml.safe_load(result)
    assert result_parsed == parsed


def test_minify_yaml_document_separator() -> None:
    text = "---\nkey: value\nlist:\n  - a"
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    parsed = yaml.safe_load(result)
    assert parsed == {"key": "value", "list": ["a"]}


def test_minify_xml_cdata() -> None:
    text = "<root><data><![CDATA[some <special> content]]></data></root>"
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert "<![CDATA[some <special> content]]>" in result


def test_minify_xml_declaration() -> None:
    text = '<?xml version="1.0"?>\n<root>\n  <item>val</item>\n</root>'
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    assert '<?xml version="1.0"?>' in result
    assert "<root><item>val</item></root>" in result


def test_minify_yaml_already_compact() -> None:
    text = "{a: 1, b: 2}"
    result = MinifyStrategy().apply(SmeltContext(text=text)).text
    # Should not error; may return unchanged or minimal change
    assert yaml.safe_load(result) == {"a": 1, "b": 2}
