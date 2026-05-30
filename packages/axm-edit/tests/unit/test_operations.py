"""Tests for axm_edit.models.operations."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_edit.models.operations import (
    BatchResult,
    CreateOp,
    DeleteOp,
    Edit,
    ReplaceOp,
)


class TestEdit:
    """Tests for the Edit model."""

    def test_valid_edit(self) -> None:
        edit = Edit(line=1, old="import os", new="import sys")
        assert edit.line == 1
        assert edit.old == "import os"
        assert edit.new == "import sys"

    def test_line_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            Edit(line=0, old="a", new="b")

    def test_old_cannot_be_empty(self) -> None:
        with pytest.raises(ValidationError):
            Edit(line=1, old="", new="b")

    def test_new_can_be_empty(self) -> None:
        """Deleting content by replacing with empty string is valid."""
        edit = Edit(line=1, old="import os", new="")
        assert edit.new == ""

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Edit(line=1, old="a", new="b", extra="nope")  # type: ignore[call-arg]


class TestReplaceOp:
    """Tests for the ReplaceOp model."""

    def test_valid_replace(self) -> None:
        op = ReplaceOp(
            file="src/foo.py",
            edits=[Edit(line=1, old="import os", new="import sys")],
        )
        assert op.op == "replace"
        assert op.file == "src/foo.py"
        assert len(op.edits) == 1

    def test_edits_cannot_be_empty(self) -> None:
        with pytest.raises(ValidationError):
            ReplaceOp(file="foo.py", edits=[])

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReplaceOp(  # type: ignore[call-arg]
                file="foo.py",
                edits=[Edit(line=1, old="a", new="b")],
                extra="nope",
            )


class TestCreateOp:
    """Tests for the CreateOp model."""

    def test_defaults(self) -> None:
        op = CreateOp(file="src/new.py", content="hello")
        assert op.op == "create"
        assert op.overwrite is False

    def test_overwrite_explicit(self) -> None:
        op = CreateOp(file="x.py", content="", overwrite=True)
        assert op.overwrite is True


class TestDeleteOp:
    """Tests for the DeleteOp model."""

    def test_valid(self) -> None:
        op = DeleteOp(file="old.py")
        assert op.op == "delete"
        assert op.file == "old.py"


class TestBatchResult:
    """Tests for the BatchResult model."""

    def test_success_defaults(self) -> None:
        result = BatchResult(success=True, applied=5)
        assert result.checkpoint is None
        assert result.summary == {"modified": 0, "created": 0, "deleted": 0}
        assert result.details == []

    def test_failure_with_details(self) -> None:
        from axm_edit.models.operations import (
            ValidationError as ValError,
        )

        result = BatchResult(
            success=False,
            error="Validation failed",
            details=[ValError(file="x.py", error="File not found")],
        )
        assert not result.success
        assert len(result.details) == 1
