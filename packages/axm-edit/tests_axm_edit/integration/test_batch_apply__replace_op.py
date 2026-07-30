"""Split from ``test_batch_apply_atomicity_security.py``.

Also covers (all ``(ReplaceOp, batch_apply)``): utf-8 fidelity on replace,
TOCTOU anchor-drift via the public ``pathlib.Path`` read seam, path-escape
rejection, whitespace/reindent behaviour, and not-found-vs-ambiguous match
disambiguation -- all exercised through the public ``batch_apply`` boundary.
"""

from __future__ import annotations

import pathlib
from pathlib import Path

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import Edit, ReplaceOp


def test_path_traversal_in_replace(tmp_project: Path) -> None:
    ops = [
        ReplaceOp(
            file="../etc/passwd",
            edits=[Edit(line=1, old="a", new="b")],
        ),
    ]
    result = batch_apply(tmp_project, ops)
    assert not result.success


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


def test_no_line_auto_search(tmp_project: Path) -> None:
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


def test_ambiguous_old_rejected(tmp_project: Path) -> None:
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


def test_old_not_found(tmp_project: Path) -> None:
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


@pytest.mark.parametrize(
    "line",
    [
        pytest.param(1, id="exact_line"),
        pytest.param(2, id="off_by_one"),
        pytest.param(6, id="off_by_five"),
        pytest.param(None, id="no_line_auto_search"),
    ],
)
def test_single_import_replace_by_line_hint(
    tmp_project: Path, line: int | None
) -> None:
    """Replacing `import os` succeeds for exact/fuzzy/no line hints."""
    ops = [
        ReplaceOp(
            file="src/foo.py",
            edits=[Edit(line=line, old="import os", new="import pathlib")],
        ),
    ]
    result = batch_apply(tmp_project, ops)
    assert result.success
    content = (tmp_project / "src" / "foo.py").read_text()
    assert "import pathlib" in content
    assert "import os" not in content


def test_old_mismatch_fails(tmp_project: Path) -> None:
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


def test_file_not_found_fails(tmp_project: Path) -> None:
    ops = [
        ReplaceOp(
            file="nope.py",
            edits=[Edit(line=1, old="a", new="b")],
        ),
    ]
    result = batch_apply(tmp_project, ops)
    assert not result.success
    assert any("not found" in (d.error or "") for d in result.details)


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


# ---------------------------------------------------------------------------
# Merged: utf-8 fidelity, TOCTOU drift, path-escape, reindent (ReplaceOp).
# ---------------------------------------------------------------------------


def test_happy_path_replace_unchanged(tmp_path: Path) -> None:
    """A single replace op applies fully with success and correct content."""
    file_a = tmp_path / "a.txt"
    file_a.write_text("original A\n", encoding="utf-8")

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="a.txt", edits=[Edit(old="original A", new="changed A")])],
    )

    assert result.success is True
    assert result.summary == {"modified": 1, "created": 0, "deleted": 0}
    assert file_a.read_text(encoding="utf-8") == "changed A\n"


def test_replace_preserves_non_ascii_utf8(tmp_path: Path) -> None:
    """A replace round-trip preserves non-ASCII bytes exactly."""
    target = tmp_path / "sample.txt"
    original = "alpha\nremplacer\nomega\n"
    target.write_text(original, encoding="utf-8")

    result = batch_apply(
        tmp_path,
        [
            ReplaceOp(
                file="sample.txt",
                edits=[Edit(old="remplacer", new="café → 中文")],
            )
        ],
    )

    assert result.success, result

    raw = target.read_bytes()
    text = raw.decode("utf-8")
    assert "café" in text
    assert "→" in text
    assert "中文" in text
    # Exact byte fidelity for the spliced non-ASCII content.
    assert "café → 中文".encode() in raw


def test_replace_aborts_when_file_drifts_between_validate_and_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """File content at the resolved range drifts after validation.

    The edit must NOT be spliced at the now-stale line location, and the
    batch must report failure for that edit (no silent wrong-location
    splice). The drift is injected through the public ``pathlib.Path`` read
    seam: on the apply-phase re-read of the target, the file is first
    mutated on disk (prepending a line) so the resolved index now points at
    ``line_a`` instead of ``ANCHOR``.
    """
    target = tmp_path / "mod.py"
    target.write_text("line_a\nANCHOR\nline_c\n", encoding="utf-8")

    drifted = "inserted_top\nline_a\nANCHOR\nline_c\n"
    real_read_text = pathlib.Path.read_text
    resolved_target = target.resolve()
    state = {"target_reads": 0}

    def drifting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        # Validation reads the target once to resolve the anchor; the apply
        # phase reads it a second time. Inject the drift right before that
        # second read so the engine's TOCTOU guard must catch it.
        if self.resolve() == resolved_target:
            state["target_reads"] += 1
            if state["target_reads"] == 2:
                # Mutate on disk (write_text is NOT patched here).
                self.write_text(drifted, encoding="utf-8")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", drifting_read_text)

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="mod.py", edits=[Edit(old="ANCHOR", new="REPLACED")])],
    )

    # The stale line 2 (``line_a``) must not have been clobbered by REPLACED.
    final = target.read_text(encoding="utf-8").splitlines()
    assert final != ["inserted_top", "REPLACED", "ANCHOR", "line_c"]
    assert "line_a" in final
    # The batch surfaces the drift as a failure rather than silently splicing.
    assert result.success is False


def test_replace_unchanged_file_applies_normally(tmp_path: Path) -> None:
    """File untouched between validate and apply applies as before."""
    target = tmp_path / "mod.py"
    target.write_text("line_a\nANCHOR\nline_c\n", encoding="utf-8")

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="mod.py", edits=[Edit(old="ANCHOR", new="REPLACED")])],
    )

    assert result.success is True
    assert target.read_text(encoding="utf-8") == "line_a\nREPLACED\nline_c\n"


def test_replace_rejects_dotdot_escape(tmp_path: Path) -> None:
    """A ``../`` escape is rejected and the outside file is untouched."""
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    op = ReplaceOp(file="../outside.txt", edits=[Edit(old="secret", new="pwned")])
    result = batch_apply(root, [op])

    assert result.success is False
    assert outside.read_text(encoding="utf-8") == "secret"


def test_replace_rejects_backslash_dotdot_escape(tmp_path: Path) -> None:
    """A ``..\\`` escape shape is rejected."""
    root = tmp_path / "root"
    root.mkdir()

    op = ReplaceOp(file="..\\outside.txt", edits=[Edit(old="a", new="b")])
    result = batch_apply(root, [op])

    assert result.success is False


def test_replace_rejects_absolute_path_outside_root(tmp_path: Path) -> None:
    """An absolute path resolving outside root is rejected."""
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    op = ReplaceOp(file=str(outside), edits=[Edit(old="secret", new="pwned")])
    result = batch_apply(root, [op])

    assert result.success is False
    assert outside.read_text(encoding="utf-8") == "secret"


def test_replace_rejects_symlink_escape(tmp_path: Path) -> None:
    """A path through a symlink whose target is outside root is rejected."""
    root = tmp_path / "root"
    root.mkdir()
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    target = outside_dir / "data.txt"
    target.write_text("secret", encoding="utf-8")

    link = root / "link"
    link.symlink_to(outside_dir, target_is_directory=True)

    op = ReplaceOp(file="link/data.txt", edits=[Edit(old="secret", new="pwned")])
    result = batch_apply(root, [op])

    assert result.success is False
    assert target.read_text(encoding="utf-8") == "secret"


def test_replace_accepts_nested_in_root_path(tmp_path: Path) -> None:
    """A valid nested in-root path resolves and the op is applied."""
    root = tmp_path / "root"
    root.mkdir()
    nested = root / "pkg" / "sub"
    nested.mkdir(parents=True)
    target = nested / "file.txt"
    target.write_text("hello world\n", encoding="utf-8")

    op = ReplaceOp(
        file="pkg/sub/file.txt", edits=[Edit(old="hello world", new="hello axm")]
    )
    result = batch_apply(root, [op])

    assert result.success is True
    assert target.read_text(encoding="utf-8") == "hello axm\n"


def test_replace_tab_indented_block(tmp_path: Path) -> None:
    """A tab-indented block reindents to the detected tab prefix.

    The ``old`` anchor is supplied dedented, so the engine takes the
    indent-normalized match path and must re-apply the file block's literal
    leading whitespace (one tab) to every replacement line.
    """
    target = tmp_path / "mod.py"
    target.write_text("def f():\n\told_line_one\n\told_line_two\n", encoding="utf-8")

    op = ReplaceOp(
        file="mod.py",
        edits=[
            Edit(old="old_line_one\nold_line_two", new="new_line_one\nnew_line_two")
        ],
    )
    result = batch_apply(tmp_path, [op])

    assert result.success is True, result
    assert target.read_text(encoding="utf-8") == (
        "def f():\n\tnew_line_one\n\tnew_line_two\n"
    )


def test_replace_mixed_tab_space_block(tmp_path: Path) -> None:
    """A block indented with a tab+spaces prefix reindents to it.

    The file block shares a literal ``\\t  `` (tab + two spaces) leading
    prefix. The fix detects that exact prefix and re-applies it (rather than
    silently leaving the replacement un-dedented), preserving the relative
    four-space indent carried inside ``new``.
    """
    target = tmp_path / "mod.py"
    target.write_text("def f():\n\t  old_a\n\t  old_b\n", encoding="utf-8")

    op = ReplaceOp(
        file="mod.py",
        edits=[Edit(old="old_a\nold_b", new="new_a\n    new_b")],
    )
    result = batch_apply(tmp_path, [op])

    assert result.success is True, result
    # The detected prefix (tab + two spaces) is re-applied to every new line;
    # the relative four-space indent of ``new_b`` is preserved on top of it.
    assert target.read_text(encoding="utf-8") == (
        "def f():\n\t  new_a\n\t      new_b\n"
    )


def test_replace_first_line_misaligned_block(tmp_path: Path) -> None:
    """A block whose first line is less indented than the following lines.

    The common leading-whitespace prefix is the *shorter* first-line indent
    (four spaces); the deeper second line keeps its extra relative indent.
    Locks that the detect/dedent/reindent steps agree on the literal prefix.
    """
    target = tmp_path / "mod.py"
    target.write_text("def f():\n    if x:\n        pass\n", encoding="utf-8")

    op = ReplaceOp(
        file="mod.py",
        edits=[Edit(old="if x:\n    pass", new="while y:\n    break")],
    )
    result = batch_apply(tmp_path, [op])

    assert result.success is True, result
    assert target.read_text(encoding="utf-8") == (
        "def f():\n    while y:\n        break\n"
    )


def test_replace_space_indented_block_unchanged(tmp_path: Path) -> None:
    """The common space-indented case reindents exactly as before.

    Regression guard: a uniform four-space block must round-trip identically
    after the whitespace-model change.
    """
    target = tmp_path / "mod.py"
    target.write_text("class C:\n    old_a\n    old_b\n", encoding="utf-8")

    op = ReplaceOp(
        file="mod.py",
        edits=[Edit(old="old_a\nold_b", new="new_a\nnew_b")],
    )
    result = batch_apply(tmp_path, [op])

    assert result.success is True, result
    assert target.read_text(encoding="utf-8") == ("class C:\n    new_a\n    new_b\n")


# ---------------------------------------------------------------------------
# Merged from test_batch_apply_match_disambiguation.py: not-found vs ambiguous.
# ---------------------------------------------------------------------------


def test_replace_zero_match_reports_not_found(tmp_path: Path) -> None:
    """A zero-match replace reports not-found, never 'ambiguous'."""
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    operations = [
        ReplaceOp(file="sample.txt", edits=[Edit(old="nonexistent", new="x")]),
    ]

    result = batch_apply(tmp_path, operations)

    assert result.success is False
    assert result.details
    detail = result.details[0]
    assert detail.error is not None
    text = detail.error.lower()
    assert "not" in text and "found" in text
    assert "ambiguous" not in text
    # File untouched.
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n"


def test_replace_multi_match_reports_ambiguous_with_lines(tmp_path: Path) -> None:
    """A >=2-match replace reports the count and matching line numbers."""
    target = tmp_path / "sample.txt"
    # 'dup' appears on lines 1, 3 and 5 (1-based).
    target.write_text("dup\nother\ndup\nmore\ndup\n", encoding="utf-8")

    operations = [
        ReplaceOp(file="sample.txt", edits=[Edit(old="dup", new="x")]),
    ]

    result = batch_apply(tmp_path, operations)

    assert result.success is False
    assert result.details
    detail = result.details[0]
    assert detail.error is not None
    text = detail.error.lower()
    assert "ambiguous" in text
    # Count reported.
    assert "3" in detail.error
    # All matching 1-based line numbers reported.
    for line_no in ("1", "3", "5"):
        assert line_no in detail.error
    # Advises disambiguation via a line hint.
    assert "line" in text
    # File untouched.
    assert target.read_text(encoding="utf-8") == "dup\nother\ndup\nmore\ndup\n"


def test_replace_single_match_applies(tmp_path: Path) -> None:
    """A single-match replace resolves and applies unchanged."""
    target = tmp_path / "sample.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    operations = [
        ReplaceOp(file="sample.txt", edits=[Edit(old="beta", new="BETA")]),
    ]

    result = batch_apply(tmp_path, operations)

    assert result.success is True
    assert not result.details
    assert target.read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"


# ---------------------------------------------------------------------------
# Merged from tests/unit/test_engine.py (AXM-2030/AXM-2031): EOL preservation,
# non-UTF-8/binary validation gate, and rollback-failure surfacing on the
# public ``batch_apply`` boundary -- all real-filesystem integration tests.
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_replace_preserves_crlf(tmp_path: Path) -> None:
    """AC1: a replace on a CRLF file keeps CRLF on the untouched lines."""
    target = tmp_path / "crlf.txt"
    target.write_bytes(b"alpha\r\nbravo\r\ncharlie\r\n")

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="crlf.txt", edits=[Edit(old="bravo", new="BRAVO")])],
    )

    assert result.success is True
    raw = target.read_bytes()
    # Untouched lines keep their CRLF; only the target content changed.
    assert raw == b"alpha\r\nBRAVO\r\ncharlie\r\n"
    assert b"\r\n" in raw


@pytest.mark.integration
def test_replace_preserves_lf(tmp_path: Path) -> None:
    """AC2: a replace on an LF file stays LF (no regression)."""
    target = tmp_path / "lf.txt"
    target.write_bytes(b"alpha\nbravo\ncharlie\n")

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="lf.txt", edits=[Edit(old="bravo", new="BRAVO")])],
    )

    assert result.success is True
    raw = target.read_bytes()
    assert raw == b"alpha\nBRAVO\ncharlie\n"
    assert b"\r\n" not in raw


@pytest.mark.integration
def test_replace_binary_is_validation_failure(tmp_path: Path) -> None:
    """AC3/AC4: a binary (null-byte) file in a ReplaceOp is a validation failure.

    No raw UnicodeDecodeError escapes batch_apply; the file is left untouched.
    """
    target = tmp_path / "binary.bin"
    original = b"alpha\x00\xff\xfe\nbravo\n"
    target.write_bytes(original)

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="binary.bin", edits=[Edit(old="bravo", new="BRAVO")])],
    )

    assert result.success is False
    assert result.error is not None
    # File untouched: validation gate rejected before any write.
    assert target.read_bytes() == original


@pytest.mark.integration
def test_replace_non_utf8_is_validation_failure(tmp_path: Path) -> None:
    """AC3: a non-UTF-8 (invalid byte) file in a ReplaceOp is a validation failure.

    Bytes that are not binary by null/printable heuristic but still fail UTF-8
    decoding must surface as BatchResult(success=False), not an exception.
    """
    target = tmp_path / "latin1.txt"
    # 0xE9 is 'e-acute' in latin-1 but an invalid lone UTF-8 continuation byte.
    original = b"caf" + b"\xe9\n" + b"bravo\n"
    target.write_bytes(original)

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="latin1.txt", edits=[Edit(old="bravo", new="BRAVO")])],
    )

    assert result.success is False
    assert result.error is not None
    assert target.read_bytes() == original


@pytest.mark.integration
def test_is_binary_wired_in_validation(tmp_path: Path) -> None:
    """AC4: binary detection runs in the validation gate; the file is untouched."""
    target = tmp_path / "image.bin"
    original = bytes(range(256)) * 4
    target.write_bytes(original)

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="image.bin", edits=[Edit(old="\x10\x11", new="XX")])],
    )

    assert result.success is False
    assert target.read_bytes() == original
