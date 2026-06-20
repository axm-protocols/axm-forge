"""Unit tests for the node test-quality rules (mirror/pyramid/tautology/dup)."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.node.test_quality import (
    NodeTestDuplicateRule,
    NodeTestMirrorRule,
    NodeTestPyramidRule,
    NodeTestTautologyRule,
)
from axm_audit.models.results import CheckResult


def _str_list(result: CheckResult, key: str) -> list[str]:
    """Extract a list[str] detail field, typed (details values are object)."""
    value = result.details[key]
    assert isinstance(value, list)
    return value


def _node_project(tmp_path: Path) -> Path:
    """Create a node project shell with a src/ dir and return the root."""
    (tmp_path / "package.json").write_text('{"name":"pkg"}')
    (tmp_path / "src").mkdir()
    return tmp_path


class TestMirror:
    """``NodeTestMirrorRule`` checks for colocated tests."""

    def test_module_with_sibling_test_passes(self, tmp_path: Path) -> None:
        """A source module with a colocated *.test.ts is covered."""
        root = _node_project(tmp_path)
        (root / "src" / "foo.ts").write_text("export const x = 1;")
        (root / "src" / "foo.test.ts").write_text("test('x', () => {});")
        result = NodeTestMirrorRule().check(root)
        assert result.passed is True

    def test_module_without_test_flagged(self, tmp_path: Path) -> None:
        """A source module with no sibling test is flagged missing."""
        root = _node_project(tmp_path)
        (root / "src" / "bar.ts").write_text("export const y = 2;")
        result = NodeTestMirrorRule().check(root)
        assert result.passed is False
        assert "bar.ts" in _str_list(result, "missing")

    def test_index_is_exempt(self, tmp_path: Path) -> None:
        """An entry-point module (index.ts) needs no test."""
        root = _node_project(tmp_path)
        (root / "src" / "index.ts").write_text("export * from './x.js';")
        result = NodeTestMirrorRule().check(root)
        assert result.passed is True

    def test_non_node_dir_skips(self, tmp_path: Path) -> None:
        """A directory with no package.json is skipped (no false positive)."""
        result = NodeTestMirrorRule().check(tmp_path)
        assert result.passed is True
        assert "skipped" in result.message.lower()


class TestPyramid:
    """``NodeTestPyramidRule`` flags colocated unit tests doing real I/O."""

    def test_pure_unit_test_passes(self, tmp_path: Path) -> None:
        """A colocated test with no I/O is a clean unit test."""
        root = _node_project(tmp_path)
        (root / "src" / "a.test.ts").write_text(
            "test('a', () => { expect(1).toBe(1); });"
        )
        assert NodeTestPyramidRule().check(root).passed is True

    def test_io_in_colocated_unit_test_flagged(self, tmp_path: Path) -> None:
        """A colocated test touching fs is flagged as misplaced."""
        root = _node_project(tmp_path)
        (root / "src" / "b.test.ts").write_text(
            "import fs from 'fs';\ntest('b', () => { fs.readFileSync('x'); });"
        )
        result = NodeTestPyramidRule().check(root)
        assert result.passed is False
        assert "b.test.ts" in _str_list(result, "misplaced")


class TestTautology:
    """``NodeTestTautologyRule`` flags weak assertions."""

    def test_real_assertion_passes(self, tmp_path: Path) -> None:
        """A behavioral assertion is not a tautology."""
        root = _node_project(tmp_path)
        (root / "src" / "c.test.ts").write_text(
            "test('c', () => { expect(f()).toBe(3); });"
        )
        assert NodeTestTautologyRule().check(root).passed is True

    def test_expect_true_flagged(self, tmp_path: Path) -> None:
        """expect(true).toBe(true) is a tautology."""
        root = _node_project(tmp_path)
        (root / "src" / "d.test.ts").write_text(
            "test('d', () => { expect(true).toBe(true); });"
        )
        assert NodeTestTautologyRule().check(root).passed is False

    def test_self_comparison_flagged(self, tmp_path: Path) -> None:
        """expect(x).toBe(x) is a self-comparison tautology."""
        root = _node_project(tmp_path)
        (root / "src" / "e.test.ts").write_text(
            "test('e', () => { expect(value).toBe(value); });"
        )
        assert NodeTestTautologyRule().check(root).passed is False


class TestDuplicate:
    """``NodeTestDuplicateRule`` flags identical test bodies."""

    def test_distinct_bodies_pass(self, tmp_path: Path) -> None:
        """Tests with different bodies are not duplicates."""
        root = _node_project(tmp_path)
        (root / "src" / "f.test.ts").write_text(
            "test('one', () => { const a = compute(1); expect(a).toBe(1); });\n"
            "test('two', () => { const b = compute(2); expect(b).toBe(2); });\n"
        )
        assert NodeTestDuplicateRule().check(root).passed is True

    def test_identical_bodies_flagged(self, tmp_path: Path) -> None:
        """Two it/test blocks with identical bodies count as a duplicate."""
        root = _node_project(tmp_path)
        body = "const result = doThing(); expect(result).toBe(42);"
        (root / "src" / "g.test.ts").write_text(
            f"test('a', () => {{ {body} }});\ntest('b', () => {{ {body} }});\n"
        )
        result = NodeTestDuplicateRule().check(root)
        assert result.passed is False
        assert result.details["duplicate_count"] == 1
