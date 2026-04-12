from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_ast.tools.describe import DescribeTool


@pytest.fixture
def tool() -> DescribeTool:
    return DescribeTool()


@pytest.fixture
def fixture_pkg(tmp_path: Path) -> Path:
    """Create a minimal Python package with two modules."""
    pkg = tmp_path / "sample_pkg"
    pkg.mkdir()
    src = pkg / "src" / "sample_pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text('"""Sample package."""\n')
    (src / "core.py").write_text(
        '"""Core module for sample operations."""\n\n'
        "def greet(name: str) -> str:\n"
        '    """Return a greeting message."""\n'
        '    return f"Hello, {name}"\n\n'
        "def add(a: int, b: int) -> int:\n"
        '    """Add two numbers."""\n'
        "    return a + b\n\n"
        "class Processor:\n"
        '    """Processes data."""\n\n'
        "    def run(self) -> None:\n"
        '        """Run the processor."""\n'
        "        pass\n"
    )
    (src / "utils.py").write_text(
        '"""Utility helpers."""\n\n'
        "def clamp(value: int, lo: int, hi: int) -> int:\n"
        '    """Clamp value between lo and hi."""\n'
        "    return max(lo, min(hi, value))\n"
    )
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "sample-pkg"\nversion = "0.1.0"\n'
    )
    return pkg


# --- Unit tests ---


def test_describe_toc_has_text(tool: DescribeTool, fixture_pkg: Path) -> None:
    """toc mode returns non-empty text containing module names."""
    result = tool.execute(path=str(fixture_pkg), detail="toc")
    assert result.success
    assert result.text
    assert isinstance(result.text, str)
    # Should contain module names from the fixture package
    assert "core" in result.text or "sample_pkg" in result.text


def test_describe_summary_has_text(tool: DescribeTool, fixture_pkg: Path) -> None:
    """summary mode returns text containing function signatures."""
    result = tool.execute(path=str(fixture_pkg), detail="summary")
    assert result.success
    assert result.text
    assert isinstance(result.text, str)
    # Should contain function signatures
    assert "greet" in result.text or "add" in result.text


def test_describe_detailed_has_text(tool: DescribeTool, fixture_pkg: Path) -> None:
    """detailed mode returns text containing docstring fragments."""
    result = tool.execute(path=str(fixture_pkg), detail="detailed")
    assert result.success
    assert result.text
    assert isinstance(result.text, str)
    # Should contain docstring fragments
    assert "greeting" in result.text.lower() or "Add two" in result.text


def test_describe_compress_has_text(tool: DescribeTool, fixture_pkg: Path) -> None:
    """compress mode sets text equal to data['compressed']."""
    result = tool.execute(path=str(fixture_pkg), compress=True)
    assert result.success
    assert result.text
    assert result.text == result.data["compressed"]


def test_text_shorter_than_json(tool: DescribeTool, fixture_pkg: Path) -> None:
    """Text output is <=60% of the equivalent JSON length."""
    result = tool.execute(path=str(fixture_pkg), detail="summary")
    assert result.success
    assert result.text is not None
    text_len = len(result.text)
    json_len = len(json.dumps(result.data))
    assert text_len <= 0.6 * json_len, (
        f"text ({text_len}) should be \u226460% of JSON ({json_len})"
    )


# --- Functional tests ---


def test_describe_text_on_axm_ast(tool: DescribeTool) -> None:
    """Run on axm-ast itself: text present, token count <50% of JSON."""
    axm_ast_path = str(Path(__file__).resolve().parents[2])
    result = tool.execute(path=axm_ast_path, detail="summary")
    assert result.success
    assert result.text
    # Token count approximation: split on whitespace
    text_tokens = len(result.text.split())
    json_tokens = len(json.dumps(result.data).split())
    assert text_tokens < 0.5 * json_tokens, (
        f"text tokens ({text_tokens}) should be <50% of JSON tokens ({json_tokens})"
    )


# --- Edge cases ---


def test_empty_package(tool: DescribeTool, tmp_path: Path) -> None:
    """Empty package (no symbols) produces minimal text, no crash."""
    pkg = tmp_path / "empty_pkg"
    pkg.mkdir()
    src = pkg / "src" / "empty_pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "empty-pkg"\nversion = "0.1.0"\n'
    )
    for detail in ("toc", "summary", "detailed"):
        result = tool.execute(path=str(pkg), detail=detail)
        assert result.success
        assert result.text is not None


def test_single_module(tool: DescribeTool, tmp_path: Path) -> None:
    """Single-module package renders that one module in text."""
    pkg = tmp_path / "single_pkg"
    pkg.mkdir()
    src = pkg / "src" / "single_pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "only.py").write_text(
        '"""The only module."""\n\ndef solo() -> None:\n    pass\n'
    )
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "single-pkg"\nversion = "0.1.0"\n'
    )
    result = tool.execute(path=str(pkg), detail="summary")
    assert result.success
    assert result.text
    assert "only" in result.text.lower() or "solo" in result.text.lower()


def test_modules_filter(tool: DescribeTool, fixture_pkg: Path) -> None:
    """Filtering by modules=['core'] only shows core module in text."""
    result = tool.execute(path=str(fixture_pkg), detail="summary", modules=["core"])
    assert result.success
    assert result.text
    assert "core" in result.text.lower()
    # utils symbols should NOT appear in filtered output
    assert "clamp" not in result.text
