from __future__ import annotations

from typing import Any

import pytest

from axm_smelt.core.counter import count


def test_count_basic() -> None:
    result = count("hello world")
    assert isinstance(result, int)
    assert result > 0


def test_count_empty() -> None:
    result = count("")
    assert isinstance(result, int)
    assert result >= 0


def test_count_whitespace_only() -> None:
    """Whitespace string returns token count > 0."""
    result = count("   \n\t  ")
    assert isinstance(result, int)
    assert result > 0


def test_count_unicode() -> None:
    """Unicode/emoji text returns valid token count."""
    result = count("\u00e9\u00e8\u00ea \U0001f600\U0001f4a1")
    assert isinstance(result, int)
    assert result > 0


def test_count_model_parameter() -> None:
    """Different model encodings each return valid counts."""
    text = "The quick brown fox jumps over the lazy dog."
    for model in ("o200k_base", "cl100k_base"):
        result = count(text, model=model)
        assert isinstance(result, int)
        assert result > 0


def test_count_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """When tiktoken is unavailable, falls back to len // 4."""
    import builtins

    real_import = builtins.__import__

    def _block_tiktoken(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "tiktoken":
            raise ImportError("mocked")
        return real_import(name, *args, **kwargs)

    import builtins as _b

    monkeypatch.setattr(_b, "__import__", _block_tiktoken)
    result = count("abcdefghijklmnop")  # 16 chars -> 4
    assert result == 4
