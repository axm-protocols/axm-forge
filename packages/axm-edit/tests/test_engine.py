"""Tests for axm_edit.core.engine — batch file editing."""

from __future__ import annotations

from pathlib import Path

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import (
    CreateOp,
    DeleteOp,
    Edit,
    Operation,
    ReplaceOp,
)


class TestSingleReplace:
    """Tests for single-file replace operations."""

    def test_single_line_replace(self, tmp_project: Path) -> None:
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[Edit(line=1, old="import os", new="import pathlib")],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert "import os" not in content

    def test_multiple_edits_same_file(self, tmp_project: Path) -> None:
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

    def test_old_mismatch_fails(self, tmp_project: Path) -> None:
        """If `old` doesn't match file content, nothing is touched."""
        original = (tmp_project / "src" / "foo.py").read_text()
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[Edit(line=1, old="WRONG", new="import pathlib")],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert result.error == "Validation failed"
        assert len(result.details) >= 1
        # File must be untouched
        assert (tmp_project / "src" / "foo.py").read_text() == original

    def test_file_not_found_fails(self, tmp_project: Path) -> None:
        ops = [
            ReplaceOp(
                file="nope.py",
                edits=[Edit(line=1, old="a", new="b")],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("not found" in (d.error or "") for d in result.details)


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


class TestMultiLineEdit:
    """Tests for multi-line old/new replacements."""

    def test_multi_line_old(self, tmp_project: Path) -> None:
        """old=`import os\\nimport sys` should match lines 1-2."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(
                        line=1,
                        old="import os\nimport sys",
                        new="import pathlib",
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert content.startswith("import pathlib\n")
        assert "import os" not in content
        assert "import sys" not in content


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


class TestMergeSameFile:
    """Tests for merging edits from multiple ReplaceOps."""

    def test_two_replace_ops_same_file(self, tmp_project: Path) -> None:
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=1, old="import os", new="import pathlib"),
                ],
            ),
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=2, old="import sys", new="import json"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert "import json" in content
        # Merged into 1 file modification
        assert result.summary["modified"] == 1


class TestCreate:
    """Tests for create operations."""

    def test_create_new_file(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="src/new.py", content='"""New module."""\n')]
        result = batch_apply(tmp_project, ops)
        assert result.success
        path = tmp_project / "src" / "new.py"
        assert path.exists()
        assert path.read_text() == '"""New module."""\n'
        assert result.summary["created"] == 1

    def test_create_existing_fails(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="src/foo.py", content="overwrite")]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("already exists" in (d.error or "") for d in result.details)

    def test_create_with_overwrite(self, tmp_project: Path) -> None:
        ops = [
            CreateOp(
                file="src/foo.py",
                content="overwritten\n",
                overwrite=True,
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        assert (tmp_project / "src" / "foo.py").read_text() == "overwritten\n"

    def test_create_nested_dirs(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="src/auth/__init__.py", content="")]
        result = batch_apply(tmp_project, ops)
        assert result.success
        assert (tmp_project / "src" / "auth" / "__init__.py").exists()


class TestDelete:
    """Tests for delete operations."""

    def test_delete_file(self, tmp_project: Path) -> None:
        ops = [DeleteOp(file="README.md")]
        result = batch_apply(tmp_project, ops)
        assert result.success
        assert not (tmp_project / "README.md").exists()
        assert result.summary["deleted"] == 1

    def test_delete_missing_fails(self, tmp_project: Path) -> None:
        ops = [DeleteOp(file="nonexistent.py")]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("not found" in (d.error or "") for d in result.details)


class TestMixedOperations:
    """Tests for mixed operation batches."""

    def test_replace_create_delete(self, tmp_project: Path) -> None:
        ops: list[Operation] = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=1, old="import os", new="import pathlib"),
                ],
            ),
            CreateOp(file="src/new.py", content='"""new."""\n'),
            DeleteOp(file="README.md"),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        assert result.applied == 3  # 1 edit + 1 create + 1 delete
        assert result.summary == {
            "modified": 1,
            "created": 1,
            "deleted": 1,
        }
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert (tmp_project / "src" / "new.py").exists()
        assert not (tmp_project / "README.md").exists()


class TestSecurity:
    """Tests for security constraints."""

    def test_path_traversal_rejected(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="../etc/passwd", content="hacked")]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("traversal" in (d.error or "").lower() for d in result.details)

    def test_path_traversal_in_replace(self, tmp_project: Path) -> None:
        ops = [
            ReplaceOp(
                file="../etc/passwd",
                edits=[Edit(line=1, old="a", new="b")],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success

    def test_path_traversal_in_delete(self, tmp_project: Path) -> None:
        ops = [DeleteOp(file="../etc/passwd")]
        result = batch_apply(tmp_project, ops)
        assert not result.success


class TestAtomicity:
    """Tests that partial failures leave the project untouched."""

    def test_valid_and_invalid_mix(self, tmp_project: Path) -> None:
        """One valid + one invalid operation → nothing applied."""
        original_foo = (tmp_project / "src" / "foo.py").read_text()
        ops: list[Operation] = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=1, old="import os", new="import pathlib"),
                ],
            ),
            DeleteOp(file="nonexistent.py"),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        # foo.py must be untouched
        assert (tmp_project / "src" / "foo.py").read_text() == original_foo


class TestFuzzyLineMatching:
    """Tests for fuzzy line-hint search (new behavior)."""

    def test_exact_line_still_works(self, tmp_project: Path) -> None:
        """Exact line number with matching old → works (regression)."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=1, old="import os", new="import pathlib"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content

    def test_line_off_by_one(self, tmp_project: Path) -> None:
        """line=2, but 'import os' is at line 1 → still found."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=2, old="import os", new="import pathlib"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert "import os" not in content

    def test_line_off_by_five(self, tmp_project: Path) -> None:
        """line=6, but 'import os' is at line 1 → found within ±5."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=6, old="import os", new="import pathlib"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content

    def test_no_line_auto_search(self, tmp_project: Path) -> None:
        """line=None → searches entire file for `old`."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(old="def hello():", new="def hello(x: int):"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "def hello(x: int):" in content

    def test_ambiguous_old_rejected(self, tmp_project: Path) -> None:
        """old appears multiple times, no line hint → rejected."""
        # Write a file with duplicate content
        (tmp_project / "src" / "dup.py").write_text(
            "x = 1\nx = 1\ny = 2\n",
        )
        ops = [
            ReplaceOp(
                file="src/dup.py",
                edits=[Edit(old="x = 1", new="x = 99")],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("ambiguous" in (d.error or "").lower() for d in result.details)

    def test_old_not_found(self, tmp_project: Path) -> None:
        """old content doesn't exist anywhere → rejected."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(old="NONEXISTENT_CONTENT", new="whatever"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("not found" in (d.error or "").lower() for d in result.details)

    def test_multi_file_fuzzy(self, tmp_project: Path) -> None:
        """Fuzzy matching across multiple files in one batch."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    # Off by 1 — import os is at L1, hint says L2
                    Edit(
                        line=2,
                        old="import os",
                        new="import pathlib",
                    ),
                ],
            ),
            ReplaceOp(
                file="src/bar.py",
                edits=[
                    # No line hint at all
                    Edit(old="import foo", new="import baz"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        foo = (tmp_project / "src" / "foo.py").read_text()
        bar = (tmp_project / "src" / "bar.py").read_text()
        assert "import pathlib" in foo
        assert "import baz" in bar
        assert result.summary["modified"] == 2


class TestIndentNormalized:
    """Tests for indent-normalized matching (agent doesn't need indentation)."""

    def test_method_without_indentation(self, tmp_project: Path) -> None:
        """old='def hello():' matches '    def hello():' in file."""
        # foo.py has 'def hello():' at line 4 with no indent (top-level)
        # Let's create a file with indented content
        (tmp_project / "src" / "indented.py").write_text(
            "class Foo:\n    def bar(self):\n        return 42\n",
        )
        ops = [
            ReplaceOp(
                file="src/indented.py",
                edits=[
                    Edit(
                        old="def bar(self):\n    return 42",
                        new="def bar(self):\n    return 99",
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "indented.py").read_text()
        assert "return 99" in content

    def test_indented_with_line_hint(self, tmp_project: Path) -> None:
        """line hint + unindented old → found via dedent fallback."""
        (tmp_project / "src" / "cls.py").write_text(
            "class MyClass:\n    x = 1\n    y = 2\n    z = 3\n",
        )
        ops = [
            ReplaceOp(
                file="src/cls.py",
                edits=[
                    Edit(
                        line=3,
                        old="y = 2",
                        new="y = 200",
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "cls.py").read_text()
        assert "y = 200" in content

    def test_multi_line_indented_block(self, tmp_project: Path) -> None:
        """Multi-line old without indentation matches indented block."""
        (tmp_project / "src" / "deep.py").write_text(
            "class Outer:\n"
            "    class Inner:\n"
            "        def method(self):\n"
            '            print("hello")\n'
            "            return True\n",
        )
        ops = [
            ReplaceOp(
                file="src/deep.py",
                edits=[
                    Edit(
                        old='def method(self):\n    print("hello")\n    return True',
                        new='def method(self):\n    print("goodbye")\n    return False',
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "deep.py").read_text()
        assert "goodbye" in content
        assert "return False" in content

    def test_exact_preferred_over_dedented(self, tmp_project: Path) -> None:
        """Exact match takes priority over dedent match."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(
                        line=1,
                        old="import os",
                        new="import pathlib",
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content


class TestIndentPreservation:
    """Tests that new content is re-indented when old was matched via dedent."""

    def test_single_line_reindent(self, tmp_project: Path) -> None:
        """Unindented old matches indented file line; new gets file indent."""
        indented_file = tmp_project / "src" / "indent.py"
        indented_file.write_text(
            'class Foo:\n    """Old docstring."""\n    pass\n',
        )
        ops = [
            ReplaceOp(
                file="src/indent.py",
                edits=[
                    Edit(
                        old='"""Old docstring."""',
                        new='"""New docstring."""',
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = indented_file.read_text()
        assert '    """New docstring."""' in content

    def test_multi_line_block_reindent(self, tmp_project: Path) -> None:
        """Multi-line unindented old; new re-indented to file level."""
        indented_file = tmp_project / "src" / "indent.py"
        indented_file.write_text(
            "class Foo:\n"
            "    def greet(self) -> str:\n"
            '        """Say hello."""\n'
            '        return "hello"\n',
        )
        ops = [
            ReplaceOp(
                file="src/indent.py",
                edits=[
                    Edit(
                        old=(
                            "def greet(self) -> str:\n"
                            '    """Say hello."""\n'
                            '    return "hello"'
                        ),
                        new=(
                            "def greet(self) -> str:\n"
                            '    """Say goodbye."""\n'
                            '    return "goodbye"'
                        ),
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = indented_file.read_text()
        assert "    def greet(self) -> str:\n" in content
        assert '        """Say goodbye."""\n' in content
        assert '        return "goodbye"\n' in content

    def test_nested_indent_preserved(self, tmp_project: Path) -> None:
        """Old at 8-space indent; new re-indented to 8 spaces."""
        indented_file = tmp_project / "src" / "indent.py"
        indented_file.write_text(
            "class Foo:\n"
            "    def method(self) -> None:\n"
            "        if True:\n"
            "            x = 1\n"
            "            y = 2\n",
        )
        ops = [
            ReplaceOp(
                file="src/indent.py",
                edits=[
                    Edit(
                        old="x = 1\ny = 2",
                        new="a = 10\nb = 20",
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = indented_file.read_text()
        assert "            a = 10\n" in content
        assert "            b = 20\n" in content

    def test_exact_match_no_reindent(self, tmp_project: Path) -> None:
        """When old includes correct indent, no extra indent is applied."""
        indented_file = tmp_project / "src" / "indent.py"
        indented_file.write_text(
            "class Foo:\n    x = 1\n    y = 2\n",
        )
        ops = [
            ReplaceOp(
                file="src/indent.py",
                edits=[
                    Edit(
                        old="    x = 1",
                        new="    x = 99",
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = indented_file.read_text()
        assert "    x = 99\n" in content
        assert "        x = 99" not in content  # Must NOT double-indent


class TestSmartNormalization:
    """Tests for smart normalization fallback in old-string matching."""

    def test_smart_quotes_normalized(self, tmp_project: Path) -> None:
        """Smart (curly) quotes in old are normalized to straight quotes."""
        (tmp_project / "src" / "quotes.py").write_text(
            'greeting = "hello"\n',
        )
        ops = [
            ReplaceOp(
                file="src/quotes.py",
                edits=[
                    Edit(
                        old="greeting = \u201chello\u201d",
                        new='greeting = "world"',
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "quotes.py").read_text()
        assert 'greeting = "world"' in content

    def test_wrapped_quotes_stripped(self, tmp_project: Path) -> None:
        """Extra wrapping quotes around old are stripped for matching."""
        (tmp_project / "src" / "wrap.py").write_text(
            "hello world\n",
        )
        ops = [
            ReplaceOp(
                file="src/wrap.py",
                edits=[
                    Edit(
                        old='"hello world"',
                        new="goodbye world",
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "wrap.py").read_text()
        assert "goodbye world" in content

    def test_no_false_positive_ambiguous(self, tmp_project: Path) -> None:
        """Normalization must not create ambiguous matches."""
        (tmp_project / "src" / "ambig.py").write_text(
            '"a"\na\n',
        )
        ops = [
            ReplaceOp(
                file="src/ambig.py",
                edits=[
                    Edit(
                        old='"a"',
                        new="b",
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        # Exact match on '"a"' is unique → should succeed (line 1)
        assert result.success
        content = (tmp_project / "src" / "ambig.py").read_text()
        assert content.startswith("b\n")

    def test_exact_match_preferred(self, tmp_project: Path) -> None:
        """When both exact and normalized match exist, exact wins."""
        (tmp_project / "src" / "both.py").write_text(
            '"hello"\nhello\n',
        )
        ops = [
            ReplaceOp(
                file="src/both.py",
                edits=[
                    Edit(
                        old='"hello"',
                        new='"world"',
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "both.py").read_text()
        # Exact match on line 1 replaced; line 2 untouched
        assert '"world"' in content
        assert "hello\n" in content

    def test_no_regression_normal_edit(self, tmp_project: Path) -> None:
        """Standard edit with correct old works as before."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(
                        line=1,
                        old="import os",
                        new="import pathlib",
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert "import os" not in content
