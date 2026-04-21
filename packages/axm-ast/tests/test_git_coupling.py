"""TDD tests for git change coupling — files that historically co-change."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_ast.core.git_coupling import git_coupled_files

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with a default branch and user config."""
    subprocess.run(
        ["git", "init"],
        cwd=path,
        capture_output=True,
        check=True,
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
        subprocess.run(
            ["git", "add", f],
            cwd=path,
            capture_output=True,
            check=True,
        )
    subprocess.run(
        ["git", "commit", "-m", message, "--allow-empty"],
        cwd=path,
        capture_output=True,
        check=True,
    )


def _make_git_project(
    tmp_path: Path,
    *,
    co_change_count: int = 5,
) -> tuple[Path, str]:
    """Create a git repo with controlled co-change history.

    Returns:
        Tuple of (project_root, target_file_relative_path).
    """
    root = tmp_path / "project"
    root.mkdir()
    _init_git_repo(root)

    # Create files
    (root / "core.py").write_text('"""Core."""\n')
    (root / "utils.py").write_text('"""Utils."""\n')
    (root / "config.py").write_text('"""Config."""\n')
    (root / "unrelated.py").write_text('"""Unrelated."""\n')

    # Initial commit with all files
    _commit(root, ["core.py", "utils.py", "config.py", "unrelated.py"], "init")

    # Co-change core.py + utils.py N times
    for i in range(co_change_count):
        (root / "core.py").write_text(f'"""Core v{i + 2}."""\n')
        (root / "utils.py").write_text(f'"""Utils v{i + 2}."""\n')
        _commit(root, ["core.py", "utils.py"], f"co-change {i + 1}")

    # Co-change core.py + config.py 2 times (below default threshold)
    for i in range(2):
        (root / "core.py").write_text(f'"""Core cfg {i}."""\n')
        (root / "config.py").write_text(f'"""Config v{i + 2}."""\n')
        _commit(root, ["core.py", "config.py"], f"config change {i + 1}")

    # Change unrelated.py alone (no coupling)
    (root / "unrelated.py").write_text('"""Unrelated v2."""\n')
    _commit(root, ["unrelated.py"], "solo change")

    return root, "core.py"


# ─── Unit: git_coupled_files ────────────────────────────────────────────────


class TestCouplingBasic:
    """Basic coupling detection."""

    def test_coupling_basic(self, tmp_path: Path) -> None:
        """Two files co-changing 5 times → returns coupling > 0.3."""
        root, target = _make_git_project(tmp_path, co_change_count=5)
        result = git_coupled_files(target, root)
        assert len(result) >= 1
        # utils.py should be coupled
        coupled_files = [r["file"] for r in result]
        assert "utils.py" in coupled_files
        # Strength should be > 0.3
        utils_entry = next(r for r in result if r["file"] == "utils.py")
        assert utils_entry["strength"] > 0.3
        assert utils_entry["co_changes"] >= 3

    def test_coupling_below_threshold(self, tmp_path: Path) -> None:
        """Only 1 co-change → returns empty (below threshold)."""
        root, target = _make_git_project(tmp_path, co_change_count=1)
        # With 1 co-change, utils.py has co_changes=1 which is < 3
        result = git_coupled_files(target, root)
        # utils.py should NOT be in results (below min_co_changes=3)
        coupled_files = [r["file"] for r in result]
        assert "utils.py" not in coupled_files

    def test_coupling_strength_formula(self, tmp_path: Path) -> None:
        """Verify exact formula: co_changes(A,B) / max(changes(A), changes(B))."""
        root, target = _make_git_project(tmp_path, co_change_count=5)
        result = git_coupled_files(target, root)
        utils_entry = next(r for r in result if r["file"] == "utils.py")

        # utils.py co-changes with core.py 5 times (+1 initial commit = 6 total)
        # core.py has: 1 init + 5 co-change + 2 config-change = 8 total commits
        # utils.py has: 1 init + 5 co-change = 6 total commits
        # co_changes(core, utils) = 6 (init + 5 co-changes)
        # coupling = 6 / max(8, 6) = 6/8 = 0.75
        assert utils_entry["co_changes"] == 6
        assert abs(utils_entry["strength"] - 0.75) < 0.01

    def test_no_git_repo(self, tmp_path: Path) -> None:
        """Run in tmpdir without git → returns empty list, no error."""
        result = git_coupled_files("some_file.py", tmp_path)
        assert result == []


class TestCouplingThresholds:
    """Threshold parameter tests."""

    def test_custom_min_strength(self, tmp_path: Path) -> None:
        """Custom min_strength filters results."""
        root, target = _make_git_project(tmp_path, co_change_count=5)
        # With high threshold, even strong coupling is filtered
        result = git_coupled_files(target, root, min_strength=0.99)
        assert result == []

    def test_custom_min_co_changes(self, tmp_path: Path) -> None:
        """Custom min_co_changes filters results."""
        root, target = _make_git_project(tmp_path, co_change_count=5)
        # config.py co-changes 3 times (init + 2) — with min=4 it's excluded
        result = git_coupled_files(target, root, min_co_changes=4)
        coupled_files = [r["file"] for r in result]
        assert "config.py" not in coupled_files


# ─── Edge cases ─────────────────────────────────────────────────────────────


class TestCouplingEdgeCases:
    """Edge cases for git coupling."""

    def test_shallow_clone(self, tmp_path: Path) -> None:
        """Shallow clone with --depth 1 → returns empty, no crash."""
        root, target = _make_git_project(tmp_path, co_change_count=5)

        # Create a shallow clone
        clone = tmp_path / "shallow"
        subprocess.run(
            ["git", "clone", "--depth", "1", f"file://{root}", str(clone)],
            capture_output=True,
            check=True,
        )
        # Shallow clone has only 1 commit → no co-change pairs
        result = git_coupled_files(target, clone)
        assert result == []  # shallow clone: 1 commit, no co-change pairs

    def test_new_file_no_history(self, tmp_path: Path) -> None:
        """File with 0 git history → returns empty."""
        root, _ = _make_git_project(tmp_path, co_change_count=3)
        # Query a file that doesn't exist in any commit
        result = git_coupled_files("brand_new.py", root)
        assert result == []

    def test_binary_files_filtered(self, tmp_path: Path) -> None:
        """Git log with binary files (images) → filtered out."""
        root = tmp_path / "binproject"
        root.mkdir()
        _init_git_repo(root)

        (root / "main.py").write_text('"""Main."""\n')
        (root / "logo.png").write_bytes(b"\x89PNG\r\n")
        _commit(root, ["main.py", "logo.png"], "init")

        for i in range(4):
            (root / "main.py").write_text(f'"""Main v{i + 2}."""\n')
            (root / "logo.png").write_bytes(b"\x89PNG\r\n" + bytes([i]))
            _commit(root, ["main.py", "logo.png"], f"change {i}")

        result = git_coupled_files("main.py", root)
        # Binary files should be filtered
        coupled_files = [r["file"] for r in result]
        assert "logo.png" not in coupled_files

    def test_subdirectory_files(self, tmp_path: Path) -> None:
        """Files in subdirectories work correctly."""
        root = tmp_path / "subdir_project"
        root.mkdir()
        _init_git_repo(root)

        (root / "src").mkdir()
        (root / "src" / "core.py").write_text('"""Core."""\n')
        (root / "src" / "utils.py").write_text('"""Utils."""\n')
        _commit(root, ["src/core.py", "src/utils.py"], "init")

        for i in range(4):
            (root / "src" / "core.py").write_text(f'"""Core v{i + 2}."""\n')
            (root / "src" / "utils.py").write_text(f'"""Utils v{i + 2}."""\n')
            _commit(root, ["src/core.py", "src/utils.py"], f"change {i}")

        result = git_coupled_files("src/core.py", root)
        coupled_files = [r["file"] for r in result]
        assert "src/utils.py" in coupled_files

    def test_result_sorted_by_strength(self, tmp_path: Path) -> None:
        """Results are sorted by strength descending."""
        root, target = _make_git_project(tmp_path, co_change_count=5)
        result = git_coupled_files(target, root, min_co_changes=1, min_strength=0.0)
        if len(result) >= 2:
            strengths = [r["strength"] for r in result]
            assert strengths == sorted(strengths, reverse=True)


# ─── Functional: integration with analyze_impact ────────────────────────────


class TestImpactWithCoupling:
    """Test git coupling integration in analyze_impact."""

    def test_impact_has_git_coupled_field(self, tmp_path: Path) -> None:
        """analyze_impact result includes git_coupled field."""
        from axm_ast.core.impact import analyze_impact

        root = tmp_path / "project"
        root.mkdir()
        _init_git_repo(root)

        # Create a package
        pkg = root / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "core.py").write_text(
            '"""Core."""\ndef helper() -> None:\n    """Help."""\n    pass\n'
        )
        _commit(root, ["pkg/__init__.py", "pkg/core.py"], "init")

        result = analyze_impact(pkg, "helper", project_root=root)
        assert "git_coupled" in result
        assert isinstance(result["git_coupled"], list)

    def test_impact_git_coupled_with_history(self, tmp_path: Path) -> None:
        """Symbol in file with coupling history → git_coupled is populated."""
        from axm_ast.core.impact import analyze_impact

        root = tmp_path / "project"
        root.mkdir()
        _init_git_repo(root)

        # Create a package
        pkg = root / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "core.py").write_text(
            '"""Core."""\ndef helper() -> None:\n    """Help."""\n    pass\n'
        )
        (pkg / "utils.py").write_text('"""Utils."""\n')
        _commit(root, ["pkg/__init__.py", "pkg/core.py", "pkg/utils.py"], "init")

        # Co-change core.py + utils.py 5 times
        for i in range(5):
            (pkg / "core.py").write_text(
                f'"""Core v{i + 2}."""\n'
                "def helper() -> None:\n"
                '    """Help."""\n'
                "    pass\n"
            )
            (pkg / "utils.py").write_text(f'"""Utils v{i + 2}."""\n')
            _commit(root, ["pkg/core.py", "pkg/utils.py"], f"co-change {i}")

        result = analyze_impact(pkg, "helper", project_root=root)
        assert len(result["git_coupled"]) >= 1
        coupled_files = [c["file"] for c in result["git_coupled"]]
        assert any("utils" in f for f in coupled_files)

    def test_impact_score_with_coupling(self, tmp_path: Path) -> None:
        """Coupling increases impact score vs without."""
        from axm_ast.core.impact import score_impact

        # Without coupling
        result_no_coupling: dict[str, object] = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [],
        }
        score_without = score_impact(result_no_coupling)

        # With coupling (3 coupled files)
        result_with_coupling: dict[str, object] = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
            "git_coupled": [
                {"file": "a.py", "strength": 0.8, "co_changes": 10},
                {"file": "b.py", "strength": 0.5, "co_changes": 5},
                {"file": "c.py", "strength": 0.4, "co_changes": 4},
            ],
        }
        score_with = score_impact(result_with_coupling)

        # Score should be higher with coupling
        levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        assert levels[score_with] > levels[score_without]

    @pytest.mark.skipif(
        not (Path(__file__).parent.parent / ".git").exists(),
        reason="Not in a git repo",
    )
    def test_impact_on_real_symbol_has_coupling(self) -> None:
        """Dogfood: analyze_impact on real symbol includes git_coupled."""
        from axm_ast.core.impact import analyze_impact

        root = Path(__file__).parent.parent
        ast_dir = root / "src" / "axm_ast"
        if ast_dir.exists():
            result = analyze_impact(ast_dir, "get_package", project_root=root)
            # Just verify the field exists, coupling may or may not have results
            assert "git_coupled" in result
            assert isinstance(result["git_coupled"], list)
