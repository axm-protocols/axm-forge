"""Tests for ValidationFeedback, WitnessResult, and WitnessRule Protocol."""

from __future__ import annotations

from typing import Any

from axm.witnesses import ValidationFeedback, WitnessResult, WitnessRule


class TestValidationFeedback:
    def test_to_dict_round_trip(self) -> None:
        feedback = ValidationFeedback(
            what="paragraph too short",
            why="expected >= 3 sentences, got 1",
            how="add 2 more sentences explaining context",
        )
        assert feedback.to_dict() == {
            "what": "paragraph too short",
            "why": "expected >= 3 sentences, got 1",
            "how": "add 2 more sentences explaining context",
        }

    def test_fields_are_addressable(self) -> None:
        feedback = ValidationFeedback(what="w", why="y", how="h")
        assert feedback.what == "w"
        assert feedback.why == "y"
        assert feedback.how == "h"


class TestWitnessResultSuccess:
    def test_success_minimal(self) -> None:
        result = WitnessResult.success()
        assert result.passed is True
        assert result.feedback is None
        assert result.verdict is None
        assert result.metadata == {}

    def test_success_with_verdict(self) -> None:
        result = WitnessResult.success(verdict="approved")
        assert result.passed is True
        assert result.verdict == "approved"
        assert result.metadata == {}

    def test_success_with_metadata(self) -> None:
        result = WitnessResult.success(metadata={"sentence_count": 5})
        assert result.passed is True
        assert result.metadata == {"sentence_count": 5}

    def test_success_metadata_none_normalized_to_empty_dict(self) -> None:
        # Implementation accepts None and defaults it; result must still be a
        # mutable empty dict rather than leak None to consumers.
        result = WitnessResult.success(metadata=None)
        assert result.metadata == {}


class TestWitnessResultFailure:
    def test_failure_carries_feedback(self) -> None:
        feedback = ValidationFeedback(what="w", why="y", how="h")
        result = WitnessResult.failure(feedback)
        assert result.passed is False
        assert result.feedback is feedback
        assert result.verdict is None
        assert result.metadata == {}

    def test_failure_with_verdict_routes_gate(self) -> None:
        feedback = ValidationFeedback(what="w", why="y", how="h")
        result = WitnessResult.failure(feedback, verdict="retry_with_feedback")
        assert result.passed is False
        assert result.verdict == "retry_with_feedback"

    def test_failure_metadata_none_normalized_to_empty_dict(self) -> None:
        feedback = ValidationFeedback(what="w", why="y", how="h")
        result = WitnessResult.failure(feedback, metadata=None)
        assert result.metadata == {}

    def test_failure_metadata_preserved(self) -> None:
        feedback = ValidationFeedback(what="w", why="y", how="h")
        result = WitnessResult.failure(feedback, metadata={"attempt": 2})
        assert result.metadata == {"attempt": 2}


class TestWitnessResultDirect:
    def test_direct_instantiation_defaults(self) -> None:
        # Bypass the helpers — confirms the dataclass defaults match what
        # success() / failure() rely on.
        result = WitnessResult(passed=True)
        assert result.feedback is None
        assert result.verdict is None
        assert result.metadata == {}

    def test_metadata_default_is_independent_per_instance(self) -> None:
        # Guards against the mutable-default-argument anti-pattern.
        a = WitnessResult(passed=True)
        b = WitnessResult(passed=True)
        a.metadata["k"] = 1
        assert b.metadata == {}


class TestWitnessRuleProtocol:
    """Verify that a concrete class satisfies the WitnessRule Protocol."""

    def test_concrete_rule_satisfies_protocol(self) -> None:
        class AlwaysPasses:
            def validate(self, content: str, **kwargs: Any) -> WitnessResult:
                return WitnessResult.success(metadata={"length": len(content)})

        rule: WitnessRule = AlwaysPasses()
        result = rule.validate("hello")
        assert result.passed is True
        assert result.metadata == {"length": 5}

    def test_failing_rule_emits_actionable_feedback(self) -> None:
        class MinLengthRule:
            def __init__(self, minimum: int) -> None:
                self.minimum = minimum

            def validate(self, content: str, **kwargs: Any) -> WitnessResult:
                if len(content) >= self.minimum:
                    return WitnessResult.success()
                return WitnessResult.failure(
                    ValidationFeedback(
                        what="content too short",
                        why=f"expected >= {self.minimum} chars, got {len(content)}",
                        how=f"add at least {self.minimum - len(content)} more chars",
                    ),
                    verdict="retry",
                )

        rule: WitnessRule = MinLengthRule(minimum=10)
        ok = rule.validate("plenty of content here")
        assert ok.passed is True

        ko = rule.validate("short")
        assert ko.passed is False
        assert ko.verdict == "retry"
        assert ko.feedback is not None
        assert ko.feedback.what == "content too short"
        assert "5" in ko.feedback.why

    def test_rule_can_use_kwargs(self) -> None:
        class StrictRule:
            def validate(self, content: str, **kwargs: Any) -> WitnessResult:
                # Demonstrates that arbitrary kwargs flow through to rules.
                if kwargs.get("strict") and not content.isupper():
                    return WitnessResult.failure(
                        ValidationFeedback(
                            what="not upper", why="strict=True", how="upper it"
                        )
                    )
                return WitnessResult.success()

        rule: WitnessRule = StrictRule()
        assert rule.validate("hello").passed is True
        assert rule.validate("hello", strict=True).passed is False
        assert rule.validate("HELLO", strict=True).passed is True
