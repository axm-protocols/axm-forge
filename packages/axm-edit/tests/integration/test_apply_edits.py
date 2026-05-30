"""Integration tests for applying old/new JSON edits to real files."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.services.lint import apply_edits

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def src_file(tmp_path: Path) -> Path:
    """A simple Python source file for edit tests."""
    f = tmp_path / "example.py"
    f.write_text("x = 1\ny = 2\n")
    return f


# ---------------------------------------------------------------------------
# Integration tests — apply_edits
# ---------------------------------------------------------------------------


class TestApplyEditsReplace:
    """old text found -> replaced with new text."""

    def test_apply_edits_replace(self, src_file: Path) -> None:
        edits = [{"old": "x = 1", "new": "_ = 1"}]
        result = apply_edits(src_file, edits)
        assert result is True
        assert src_file.read_text() == "_ = 1\ny = 2\n"


class TestApplyEditsInsert:
    """old anchor, new = anchor + extra lines -> insertion applied to file."""

    @pytest.mark.parametrize(
        ("initial", "edits", "expected"),
        [
            pytest.param(
                "import os\n\ndef f(): pass",
                [{"old": "import os", "new": "import os\nimport logging"}],
                "import logging",
                id="anchor-import",
            ),
            pytest.param(
                "x = 1\r\ny = 2\r\n",
                [{"old": "x = 1", "new": "_ = 1"}],
                "_ = 1",
                id="crlf-normalization",
            ),
            pytest.param(
                "def main():\n    print('hello')\n",
                [
                    {
                        "old": "def main():\n    print('hello')",
                        "new": "def main():\n    logging.info('start')\n"
                        "    print('hello')",
                    }
                ],
                "logging.info('start')",
                id="multiline-anchor",
            ),
        ],
    )
    def test_apply_edits_insert(
        self,
        tmp_path: Path,
        initial: str,
        edits: list[dict[str, str]],
        expected: str,
    ) -> None:
        f = tmp_path / "ins.py"
        f.write_text(initial)
        result = apply_edits(f, edits)
        assert result is True
        assert expected in f.read_text()


class TestApplyEditsDelete:
    """old block, new empty -> matched block removed, siblings preserved."""

    @pytest.mark.parametrize(
        ("initial", "absent", "present"),
        [
            pytest.param(
                "import os\nimport sys\nx = 1",
                "import sys",
                ["import os", "x = 1"],
                id="three-lines",
            ),
            pytest.param(
                "import os\nimport sys\nimport json\n\nx = 1\n",
                "import sys",
                ["import os", "import json"],
                id="with-json-sibling",
            ),
        ],
    )
    def test_apply_edits_delete(
        self,
        tmp_path: Path,
        initial: str,
        absent: str,
        present: list[str],
    ) -> None:
        f = tmp_path / "del.py"
        f.write_text(initial)
        edits = [{"old": "import sys\n", "new": ""}]
        result = apply_edits(f, edits)
        assert result is True
        content = f.read_text()
        assert absent not in content
        for token in present:
            assert token in content


class TestApplyEditsNoMatch:
    """no applicable edit (missing old / empty list) -> False, file unchanged."""

    @pytest.mark.parametrize(
        "edits",
        [
            pytest.param(
                [{"old": "nonexistent text", "new": "replacement"}],
                id="old-not-found",
            ),
            pytest.param([], id="empty-array"),
        ],
    )
    def test_apply_edits_no_match(
        self,
        src_file: Path,
        edits: list[dict[str, str]],
    ) -> None:
        original = src_file.read_text()
        result = apply_edits(src_file, edits)
        assert result is False
        assert src_file.read_text() == original


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestOldMatchesMultipleTimes:
    """old appears 3 times -> only first occurrence replaced."""

    def test_first_occurrence_only(self, tmp_path: Path) -> None:
        f = tmp_path / "multi.py"
        f.write_text("pass\npass\npass\n")
        edits = [{"old": "pass", "new": "return"}]
        result = apply_edits(f, edits)
        assert result is True
        content = f.read_text()
        assert content.count("return") == 1
        assert content.count("pass") == 2


class TestVeryLargeJsonOutput:
    """Claude returns 50+ edits -> all applied sequentially."""

    def test_large_edit_list(self, tmp_path: Path) -> None:
        # Build a file with 50 unique lines
        lines = [f"var_{i} = {i}" for i in range(50)]
        f = tmp_path / "big.py"
        f.write_text("\n".join(lines) + "\n")

        # Build 50 edits
        edits = [
            {"old": f"var_{i} = {i}", "new": f"var_{i} = {i * 10}"} for i in range(50)
        ]
        result = apply_edits(f, edits)
        assert result is True
        content = f.read_text()
        for i in range(50):
            assert f"var_{i} = {i * 10}" in content


class TestMultilineReplace:
    """old spans 2 lines, new spans 3 lines -> correct replacement."""

    def test_multiline_replace(self, tmp_path: Path) -> None:
        f = tmp_path / "multi.py"
        f.write_text("try:\n    x = 1\nexcept:\n    pass\n")
        edits = [
            {
                "old": "except:\n    pass",
                "new": "except Exception as e:\n    logging.error(e)\n    raise",
            }
        ]
        result = apply_edits(f, edits)
        assert result is True
        content = f.read_text()
        assert "except Exception as e:" in content
        assert "logging.error(e)" in content
        assert "raise" in content
