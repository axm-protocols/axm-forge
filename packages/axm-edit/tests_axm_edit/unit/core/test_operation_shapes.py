"""Unit tests for axm_edit.core.operation_shapes (no real I/O)."""

from __future__ import annotations

import json
from typing import get_args

import pytest
from pydantic import BaseModel, TypeAdapter

from axm_edit.core.operation_shapes import (
    CHECKSUM_PLACEHOLDER,
    OPERATION_EXAMPLES,
    OPERATION_SHAPES_HINT,
)
from axm_edit.models.operations import Operation

VALID_DIGEST = "0" * 64
OPERATION_ADAPTER: TypeAdapter[Operation] = TypeAdapter(Operation)


def _union_members() -> tuple[type[BaseModel], ...]:
    """Operation models of the discriminated union."""
    union, _discriminator = get_args(Operation)
    return get_args(union)


def _with_valid_digest(example: dict[str, object]) -> dict[str, object]:
    """Swap the checksum placeholder for a well-formed digest."""
    if example.get("expected_checksum") != CHECKSUM_PLACEHOLDER:
        return example
    return {**example, "expected_checksum": VALID_DIGEST}


class TestOperationExamples:
    """The published examples are valid against the live schema."""

    @pytest.mark.parametrize(
        "example", OPERATION_EXAMPLES, ids=lambda ex: str(ex["op"])
    )
    def test_example_parses_through_the_operation_union(
        self, example: dict[str, object]
    ) -> None:
        """Every example validates against the Operation union."""
        parsed = OPERATION_ADAPTER.validate_python(_with_valid_digest(example))

        assert parsed.op == example["op"]

    def test_examples_cover_every_operation_kind(self) -> None:
        """A new op kind cannot ship without its published example."""
        kinds = {model.model_fields["op"].default for model in _union_members()}

        assert {example["op"] for example in OPERATION_EXAMPLES} == kinds


class TestOperationShapesHint:
    """The hint renders every example verbatim."""

    def test_hint_carries_each_example_as_json(self) -> None:
        """Each example appears as a JSON line of the hint."""
        missing = [
            example
            for example in OPERATION_EXAMPLES
            if json.dumps(example) not in OPERATION_SHAPES_HINT
        ]

        assert not missing, missing
