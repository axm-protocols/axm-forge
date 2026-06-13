"""Split from ``test_context.py``."""

from pathlib import Path

from axm_ast.core.context import detect_stack
from tests.unit._helpers import _make_pyproject


class TestDetectStack:
    """Test pyproject.toml dependency categorization."""

    def test_detect_stack_cyclopts(self, tmp_path: Path) -> None:
        """Detects cyclopts as CLI framework."""
        _make_pyproject(tmp_path, ["cyclopts>=3.0"])
        stack = detect_stack(tmp_path)
        assert "cli" in stack
        assert "cyclopts" in stack["cli"]

    def test_detect_stack_pydantic(self, tmp_path: Path) -> None:
        """Detects pydantic as models framework."""
        _make_pyproject(tmp_path, ["pydantic>=2.0"])
        stack = detect_stack(tmp_path)
        assert "models" in stack
        assert "pydantic" in stack["models"]

    def test_detect_stack_multiple(self, tmp_path: Path) -> None:
        """Categorizes all deps correctly."""
        _make_pyproject(
            tmp_path,
            ["cyclopts>=3.0", "pydantic>=2.0", "tree-sitter>=0.24"],
        )
        stack = detect_stack(tmp_path)
        assert "cyclopts" in stack["cli"]
        assert "pydantic" in stack["models"]
        assert "tree-sitter" in stack["parsing"]

    def test_detect_stack_no_pyproject(self, tmp_path: Path) -> None:
        """No pyproject.toml → empty stack."""
        stack = detect_stack(tmp_path)
        assert stack == {}

    def test_detect_stack_unknown_deps(self, tmp_path: Path) -> None:
        """Unknown deps are not categorized."""
        _make_pyproject(tmp_path, ["obscure-lib>=1.0"])
        stack = detect_stack(tmp_path)
        # obscure-lib shouldn't appear in any category
        all_deps = [d for deps in stack.values() for d in deps]
        assert "obscure-lib" not in all_deps

    def test_detect_stack_dev_deps(self, tmp_path: Path) -> None:
        """Detects dev dependencies (pytest, ruff, mypy)."""
        _make_pyproject(tmp_path, [])
        pyproject = tmp_path / "pyproject.toml"
        content = pyproject.read_text()
        content += (
            '\n[dependency-groups]\ndev = ["pytest>=8.0", "ruff>=0.8", "mypy>=1.14"]\n'
        )
        pyproject.write_text(content)
        stack = detect_stack(tmp_path)
        assert "tests" in stack
        assert "lint" in stack
        assert "types" in stack

    def test_detect_stack_build_system(self, tmp_path: Path) -> None:
        """Detects build system from [build-system]."""
        _make_pyproject(tmp_path, [], build="hatchling")
        stack = detect_stack(tmp_path)
        assert "packaging" in stack
        assert "hatchling" in stack["packaging"]

    def test_detect_stack_poetry(self, tmp_path: Path) -> None:
        """Detects poetry from build-system."""
        _make_pyproject(tmp_path, [], build="poetry.core.masonry.api")
        stack = detect_stack(tmp_path)
        assert "packaging" in stack
        assert any("poetry" in d for d in stack["packaging"])

    def test_dependencies_not_collide_with_optional(self, tmp_path: Path) -> None:
        """AC2: 'dependencies' parsed without colliding with 'optional-dependencies'.

        Runtime deps (cyclopts) are detected; optional/extra deps (flask) must
        NOT leak into the stack via the old ``dependencies`` substring match.
        """
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "demo"\n'
            'dependencies = ["cyclopts>=4.5"]\n'
            "\n"
            "[project.optional-dependencies]\n"
            'web = ["flask>=3.0"]\n',
            encoding="utf-8",
        )
        stack = detect_stack(tmp_path)
        flat = {dep for deps in stack.values() for dep in deps}
        assert "cyclopts" in flat
        assert "flask" not in flat

    def test_nested_array_dependency_parsed(self, tmp_path: Path) -> None:
        """AC2: a multi-line dependencies array with a nearby nested array is parsed.

        The old regex stopped at the first ``]`` and broke on nested arrays;
        tomllib parses the full array regardless of layout.
        """
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "demo"\n'
            "dependencies = [\n"
            '    "pydantic>=2.0",\n'
            '    "fastapi>=0.110",\n'
            "]\n"
            "\n"
            "[tool.demo]\n"
            "matrix = [[1, 2], [3, 4]]\n",
            encoding="utf-8",
        )
        flat = {dep for deps in detect_stack(tmp_path).values() for dep in deps}
        assert "pydantic" in flat
        assert "fastapi" in flat

    def test_malformed_pyproject_graceful(self, tmp_path: Path) -> None:
        """AC3: a malformed pyproject.toml degrades to an empty stack, no crash."""
        (tmp_path / "pyproject.toml").write_text(
            "[project\ndependencies = [ broken", encoding="utf-8"
        )
        assert detect_stack(tmp_path) == {}
