"""Split from ``test_batch_apply_fuzzy_matching.py``."""

from pathlib import Path

import pytest

from axm_edit.core.diagnostics import explain_difference
from axm_edit.core.engine import _validate_replace, batch_apply
from axm_edit.models.operations import Edit, ReplaceOp

# Built from its code point so the source file stays pure ASCII.
NBSP = chr(0x00A0)


class TestBottomToTop:
    """Tests for bottom-to-top edit ordering."""

    def test_adding_lines_doesnt_shift_upper(self, tmp_project: Path) -> None:
        """Edit at line 4 adds lines; edit at line 1 still works."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(
                        line=1,
                        old="import os",
                        new="import os\nimport pathlib",
                    ),
                    Edit(
                        line=4,
                        old="def hello():",
                        new='def hello(name: str = "world"):',
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert 'def hello(name: str = "world"):' in content


def test_multiple_edits_same_file(tmp_project: Path) -> None:
    ops = [
        ReplaceOp(
            file="src/foo.py",
            edits=[
                Edit(line=1, old="import os", new="import pathlib"),
                Edit(line=2, old="import sys", new="import json"),
            ],
        ),
    ]
    result = batch_apply(tmp_project, ops)
    assert result.success
    content = (tmp_project / "src" / "foo.py").read_text()
    assert "import pathlib" in content
    assert "import json" in content
    assert result.summary["modified"] == 1


class TestOverlap:
    """Tests for overlapping edit detection."""

    def test_overlapping_edits_rejected(self, tmp_project: Path) -> None:
        original = (tmp_project / "src" / "foo.py").read_text()
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(
                        line=1,
                        old="import os\nimport sys",
                        new="x",
                    ),
                    Edit(line=2, old="import sys", new="y"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        # File untouched
        assert (tmp_project / "src" / "foo.py").read_text() == original


# ---------------------------------------------------------------------------
# Merged from tests/unit/test_engine.py (AXM-2030): multi-Edit CRLF fidelity --
# a real-filesystem integration test exercising two edits in one ReplaceOp.
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_replace_preserves_crlf_multiple_edits(tmp_path: Path) -> None:
    """AC1: multiple edits on a CRLF file all preserve CRLF endings."""
    target = tmp_path / "crlf_multi.txt"
    target.write_bytes(b"one\r\ntwo\r\nthree\r\nfour\r\n")

    result = batch_apply(
        tmp_path,
        [
            ReplaceOp(
                file="crlf_multi.txt",
                edits=[
                    Edit(old="one", new="ONE"),
                    Edit(old="three", new="THREE"),
                ],
            )
        ],
    )

    assert result.success is True
    assert target.read_bytes() == b"ONE\r\ntwo\r\nTHREE\r\nfour\r\n"


@pytest.mark.integration
def test_validate_replace_truncates_ambiguous_match_lines(tmp_path: Path) -> None:
    """AC3: a real file repeating the anchor 12 times is summarised."""
    anchor = "value = compute(x)"
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    body = "import os\n" + f"{anchor}\nfiller = 0\n" * 12
    target.write_text(body, encoding="utf-8")

    resolved, errors = _validate_replace(
        tmp_path,
        "pkg/mod.py",
        [Edit(old=anchor, new="value = compute(y)")],
    )

    assert resolved == []
    assert len(errors) == 1
    message = errors[0].error
    assert message is not None
    assert "Ambiguous match:" in message
    assert "(+7 more)" in message
    assert "24" not in message


@pytest.mark.integration
def test_hinted_miss_on_a_real_file_reports_the_character_difference(
    tmp_path: Path,
) -> None:
    """AC1: a hinted miss on a real file appends the explain_difference text."""
    anchor = "value = compute(x)"
    actual_line = f"value{NBSP}= compute(x)"
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    target.write_text(f"import os\n{actual_line}\nreturn value\n", encoding="utf-8")

    resolved, errors = _validate_replace(
        tmp_path,
        "pkg/mod.py",
        [Edit(line=2, old=anchor, new="value = compute(y)")],
    )

    assert resolved == []
    assert len(errors) == 1
    message = errors[0].error
    assert message is not None
    assert "Content not found at or near hint line" in message
    assert explain_difference(anchor, actual_line) in message


@pytest.mark.integration
def test_hint_past_eof_on_a_real_file_reports_its_line_count(
    tmp_path: Path,
) -> None:
    """AC2: a hint past the end of a real 3-line file names its line count."""
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    resolved, errors = _validate_replace(
        tmp_path,
        "pkg/mod.py",
        [Edit(line=99, old="delta", new="epsilon")],
    )

    assert resolved == []
    assert len(errors) == 1
    message = errors[0].error
    assert message is not None
    assert "3 lines" in message
