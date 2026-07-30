from __future__ import annotations

from axm.hooks.base import HookResult


class TestOkWithText:
    def test_ok_with_text(self) -> None:
        result = HookResult.ok(text="hi", foo="bar")
        assert result.success is True
        assert result.text == "hi"
        assert result.metadata == {"foo": "bar"}

    def test_ok_without_text(self) -> None:
        result = HookResult.ok(foo="bar")
        assert result.success is True
        assert result.text is None
        assert result.metadata == {"foo": "bar"}

    def test_ok_text_none_explicit(self) -> None:
        result = HookResult.ok(text=None, x=1)
        assert result.success is True
        assert result.text is None
        assert result.metadata == {"x": 1}

    def test_ok_text_empty_string(self) -> None:
        result = HookResult.ok(text="", x=1)
        assert result.success is True
        assert result.text == ""
        assert result.metadata == {"x": 1}

    def test_ok_text_only_no_kwargs(self) -> None:
        result = HookResult.ok(text="hi")
        assert result.success is True
        assert result.text == "hi"
        assert result.metadata == {}


class TestFailWithText:
    def test_fail_with_text(self) -> None:
        result = HookResult.fail("err", text="detail")
        assert result.success is False
        assert result.error == "err"
        assert result.text == "detail"

    def test_fail_without_text(self) -> None:
        result = HookResult.fail("err", foo="bar")
        assert result.success is False
        assert result.error == "err"
        assert result.text is None
        assert result.metadata == {"foo": "bar"}


class TestSkip:
    def test_skip_default_reason(self) -> None:
        result = HookResult.skip()
        # Skipped hooks model "ran successfully, deliberately no-op" — gates
        # treat them as pass while keeping the skip flag observable.
        assert result.success is True
        assert result.error is None
        assert result.metadata == {"skipped": True, "reason": "condition not met"}

    def test_skip_custom_reason(self) -> None:
        result = HookResult.skip("session_id missing")
        assert result.success is True
        assert result.metadata == {"skipped": True, "reason": "session_id missing"}
