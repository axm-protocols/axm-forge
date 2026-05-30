"""Split from ``test_engine.py``."""

from __future__ import annotations

from pathlib import Path

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import Edit, ReplaceOp


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
                        old="greeting = “hello”",
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
