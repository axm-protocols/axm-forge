from __future__ import annotations

import json
from typing import Any

from axm_smelt.core.models import Format, SmeltReport
from axm_smelt.core.pipeline import check, smelt

# --- Functional tests ---


def test_smelt_json_minify() -> None:
    text = '{\n  "name": "Alice"\n}'
    report = smelt(text)
    assert isinstance(report, SmeltReport)
    assert report.savings_pct > 0
    assert "minify" in report.strategies_applied


def test_smelt_with_preset() -> None:
    text = '{\n  "name": "Alice"\n}'
    report = smelt(text, preset="safe")
    assert isinstance(report, SmeltReport)
    assert "minify" in report.strategies_applied


def test_check_no_transform(sample_json: str) -> None:
    report = check(sample_json)
    assert isinstance(report, SmeltReport)
    assert report.original == report.compacted


def test_pipeline_preserves_data() -> None:
    text = '{\n  "name": "Alice",\n  "items": [1, 2, 3]\n}'
    report = smelt(text)
    assert json.loads(report.compacted) == json.loads(text)


# --- Edge cases ---


def test_smelt_empty_input() -> None:
    report = smelt("")
    assert isinstance(report, SmeltReport)
    assert report.original_tokens >= 0


def test_smelt_already_minified() -> None:
    report = smelt('{"a":1}')
    assert isinstance(report, SmeltReport)
    assert report.savings_pct == 0


def test_smelt_large_json() -> None:
    data = {f"key_{i}": f"value_{i}" for i in range(10000)}
    text = json.dumps(data, indent=2)
    report = smelt(text)
    assert isinstance(report, SmeltReport)
    assert report.savings_pct > 0


def test_smelt_invalid_json_like_start() -> None:
    text = '{"broken": '
    report = smelt(text)
    assert isinstance(report, SmeltReport)
    assert report.format == Format.TEXT


def test_smelt_unicode_content() -> None:
    text = json.dumps({"emoji": "\U0001f680", "cjk": "\u4f60\u597d"}, indent=2)
    report = smelt(text)
    assert isinstance(report, SmeltReport)
    content = json.loads(report.compacted)
    assert content["emoji"] == "\U0001f680"
    assert content["cjk"] == "\u4f60\u597d"


def test_smelt_nested_json() -> None:
    nested: dict[str, Any] = {"level": 0}
    current: dict[str, Any] = nested
    for i in range(1, 12):
        current["child"] = {"level": i}
        current = current["child"]
    text = json.dumps(nested, indent=2)
    report = smelt(text)
    assert isinstance(report, SmeltReport)
    assert json.loads(report.compacted) == nested
