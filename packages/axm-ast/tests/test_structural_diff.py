"""Tests for structural branch diff at symbol level."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm_ast.core.structural_diff import structural_diff

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with a default branch and user config."""
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=path, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        capture_output=True,
        check=True,
    )


def _commit(path: Path, files: list[str], message: str) -> None:
    """Stage files and commit."""
    for f in files:
        subprocess.run(["git", "add", f], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=path,
        capture_output=True,
        check=True,
    )


def _make_diff_project(tmp_path: Path) -> Path:
    """Create a git repo with a 'main' and 'feature' branch for diff testing.

    On main:
        - pkg/__init__.py
        - pkg/core.py: helper(), old_func()
    On feature:
        - pkg/__init__.py
        - pkg/core.py: helper() (modified signature), new_func()
        - pkg/extras.py: bonus()
    """
    root = tmp_path / "project"
    root.mkdir()
    _init_git_repo(root)

    # Create package on main
    pkg = root / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Pkg."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n\n'
        "def helper(x: int) -> str:\n"
        '    """Help."""\n'
        "    return str(x)\n\n\n"
        "def old_func() -> None:\n"
        '    """Old."""\n'
        "    pass\n"
    )
    _commit(root, ["pkg/__init__.py", "pkg/core.py"], "initial commit")

    # Create feature branch with changes
    subprocess.run(
        ["git", "checkout", "-b", "feature"],
        cwd=root,
        capture_output=True,
        check=True,
    )

    # Modify helper (changed signature), remove old_func, add new_func
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n\n'
        "def helper(x: int, y: int = 0) -> str:\n"  # modified signature
        '    """Help."""\n'
        "    return str(x + y)\n\n\n"
        "def new_func(name: str) -> str:\n"  # added
        '    """New."""\n'
        '    return f"hello {name}"\n'
    )
    # Add new file
    (pkg / "extras.py").write_text(
        '"""Extras module."""\n\n\n'
        "def bonus() -> int:\n"
        '    """Bonus."""\n'
        "    return 42\n"
    )
    _commit(root, ["pkg/core.py", "pkg/extras.py"], "feature changes")

    # Go back to main
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=root,
        capture_output=True,
        check=True,
    )

    return root


# ─── Unit tests ──────────────────────────────────────────────────────────────


class TestDiffAddedSymbol:
    """Test detection of added symbols."""

    def test_diff_added_symbol(self, tmp_path: Path) -> None:
        """New function on feature branch appears in 'added'."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "feature")
        added_names = [s["name"] for s in result["added"]]
        assert "new_func" in added_names

    def test_diff_added_from_new_file(self, tmp_path: Path) -> None:
        """Symbols from a new file on feature appear in 'added'."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "feature")
        added_names = [s["name"] for s in result["added"]]
        assert "bonus" in added_names


class TestDiffRemovedSymbol:
    """Test detection of removed symbols."""

    def test_diff_removed_symbol(self, tmp_path: Path) -> None:
        """Function on main but not on feature appears in 'removed'."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "feature")
        removed_names = [s["name"] for s in result["removed"]]
        assert "old_func" in removed_names


class TestDiffModifiedSymbol:
    """Test detection of modified symbols."""

    def test_diff_modified_symbol(self, tmp_path: Path) -> None:
        """Same function name but different signature → 'modified'."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "feature")
        modified_names = [s["name"] for s in result["modified"]]
        assert "helper" in modified_names

    def test_diff_modified_has_old_and_new(self, tmp_path: Path) -> None:
        """Modified entry shows old and new signatures."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "feature")
        helper_mod = next(s for s in result["modified"] if s["name"] == "helper")
        assert "old_signature" in helper_mod
        assert "new_signature" in helper_mod
        assert helper_mod["old_signature"] != helper_mod["new_signature"]


class TestDiffUnchanged:
    """Test when nothing changes."""

    def test_diff_unchanged(self, tmp_path: Path) -> None:
        """Identical branches → empty diff."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "main")
        assert result["added"] == []
        assert result["removed"] == []
        assert result["modified"] == []


# ─── Functional tests ────────────────────────────────────────────────────────


class TestDiffFunctional:
    """Functional tests for structural diff."""

    def test_diff_real_branches(self, tmp_path: Path) -> None:
        """Full diff with known changes produces correct result."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "feature")

        # Verify structure
        assert "added" in result
        assert "removed" in result
        assert "modified" in result

        # Verify counts
        assert len(result["added"]) >= 2  # new_func + bonus
        assert len(result["removed"]) >= 1  # old_func
        assert len(result["modified"]) >= 1  # helper

    def test_worktree_cleanup(self, tmp_path: Path) -> None:
        """After diff, no leftover git worktrees."""
        root = _make_diff_project(tmp_path)
        structural_diff(root / "pkg", "main", "feature")

        # Check no worktrees remain (besides the main one)
        result = subprocess.run(
            ["git", "worktree", "list"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 1  # only the main worktree

    def test_result_has_summary(self, tmp_path: Path) -> None:
        """Result includes a summary section with counts."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "feature")
        assert "summary" in result
        assert result["summary"]["added"] >= 2
        assert result["summary"]["removed"] >= 1
        assert result["summary"]["modified"] >= 1

    def test_symbols_have_file_and_kind(self, tmp_path: Path) -> None:
        """Each symbol entry includes file path and kind."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "feature")
        for symbol in result["added"]:
            assert "file" in symbol
            assert "kind" in symbol
            assert "name" in symbol


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestDiffEdgeCases:
    """Edge cases for structural diff."""

    def test_same_branch(self, tmp_path: Path) -> None:
        """main..main → empty diff."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "main")
        assert result["added"] == []
        assert result["removed"] == []
        assert result["modified"] == []

    def test_nonexistent_ref(self, tmp_path: Path) -> None:
        """Invalid branch name → error dict."""
        root = _make_diff_project(tmp_path)
        result = structural_diff(root / "pkg", "main", "nonexistent-branch")
        assert result.get("error") is not None

    def test_not_a_git_repo(self, tmp_path: Path) -> None:
        """Non-git directory → error dict."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "core.py").write_text("def foo() -> None: ...\n")
        result = structural_diff(pkg, "main", "feature")
        assert result.get("error") is not None

    def test_class_added(self, tmp_path: Path) -> None:
        """Class added on feature branch appears in 'added'."""
        root = tmp_path / "project"
        root.mkdir()
        _init_git_repo(root)

        pkg = root / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "models.py").write_text('"""Models."""\n')
        _commit(root, ["pkg/__init__.py", "pkg/models.py"], "init")

        subprocess.run(
            ["git", "checkout", "-b", "feat"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        (pkg / "models.py").write_text(
            '"""Models."""\n\n\nclass User:\n    """A user."""\n\n    name: str\n'
        )
        _commit(root, ["pkg/models.py"], "add User class")
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=root,
            capture_output=True,
            check=True,
        )

        result = structural_diff(pkg, "main", "feat")
        added_names = [s["name"] for s in result["added"]]
        assert "User" in added_names

    def test_head_defaults_to_current(self, tmp_path: Path) -> None:
        """If head is HEAD, uses current branch."""
        root = _make_diff_project(tmp_path)
        # We're on main, so HEAD == main → same as main..main
        result = structural_diff(root / "pkg", "main", "HEAD")
        assert result["added"] == []
        assert result["removed"] == []
        assert result["modified"] == []
