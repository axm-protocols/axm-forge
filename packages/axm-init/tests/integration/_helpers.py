"""Shared helpers for ``tests/integration``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.integration._helpers import <name>``.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from textwrap import dedent

from axm_init.models.check import CheckResult, ProjectResult


def _publish_with(root: Path, body: str) -> Path:
    """Write a minimal publish.yml under *root* with the given body."""
    publish_yml = root / ".github" / "workflows" / "publish.yml"
    publish_yml.parent.mkdir(parents=True, exist_ok=True)
    publish_yml.write_text(body)
    return publish_yml


def _make_realistic_ci(root: Path) -> Path:
    """Create a CI workflow that mirrors the shape of real axm workflows.

    Includes a ``matrix.package`` list *and* a subsequent ``steps:``
    block with its own ``- `` items — the exact shape that triggered
    the original regression.
    """
    ci = root / ".github" / "workflows" / "ci.yml"
    ci.parent.mkdir(parents=True, exist_ok=True)
    ci.write_text(
        "name: CI\n\n"
        "on:\n  push:\n    branches: [main]\n\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    strategy:\n"
        "      fail-fast: false\n"
        "      matrix:\n"
        "        package:\n"
        "          - existing-pkg\n"
        "          - another-pkg\n"
        '        python-version: ["3.12", "3.13"]\n'
        "    steps:\n"
        "      - uses: actions/checkout@v6\n"
        "      - uses: astral-sh/setup-uv@v7\n"
        "      - run: uv sync --all-groups\n"
        "      - name: Test ${{ matrix.package }}\n"
        "        run: uv run pytest --cov\n"
    )
    return ci


def _make_realistic_publish(root: Path) -> Path:
    """Create a publish workflow mirroring real axm workflows."""
    publish = root / ".github" / "workflows" / "publish.yml"
    publish.parent.mkdir(parents=True, exist_ok=True)
    publish.write_text(
        "name: Publish to PyPI\n\n"
        "on:\n  push:\n    tags:\n"
        '      - "existing-pkg/v*"\n'
        '      - "another-pkg/v*"\n\n'
        "jobs:\n"
        "  publish:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v6\n"
        "      - uses: astral-sh/setup-uv@v7\n"
        "      - run: uv build\n"
        "      - uses: pypa/gh-action-pypi-publish@release/v1\n"
    )
    return publish


def _make_realistic_release(root: Path) -> Path:
    """Create a release workflow mirroring real axm workflows."""
    release = root / ".github" / "workflows" / "release.yml"
    release.parent.mkdir(parents=True, exist_ok=True)
    release.write_text(
        "name: Release\n\n"
        "on:\n  push:\n    tags:\n"
        '      - "existing-pkg/v*"\n\n'
        "permissions:\n  contents: write\n\n"
        "jobs:\n"
        "  release:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v6\n"
        "      - name: Detect package from tag\n"
        "        id: detect\n"
        "        run: |\n"
        "          TAG=${GITHUB_REF#refs/tags/}\n"
        '          if [[ "$TAG" == existing-pkg/* ]]; then\n'
        '            echo "package=existing-pkg" >> "$GITHUB_OUTPUT"\n'
        "          else\n"
        '            echo "::error::Unknown tag"\n'
        "            exit 1\n"
        "          fi\n"
        "      - name: Create GitHub Release\n"
        "        uses: softprops/action-gh-release@v2\n"
    )
    return release


MKDOCS_FULL = """
site_name: Test
nav:
  - Tutorial: tutorial.md
  - How-To: howto.md
  - Reference: reference.md
  - Explanation: explanation.md
plugins:
  - gen-files
  - literate-nav
  - mkdocstrings
"""
ROOT_WORKSPACE_HEADER = """\
[project]
name = "workspace"
version = "0.0.0"

[tool.uv.workspace]
members = ["packages/*"]
"""
SCAFFOLD_ARGS = [
    "--org",
    "test-org",
    "--author",
    "Test Author",
    "--email",
    "test@test.com",
]
STANDALONE_TOML = dedent("""\
    [project]
    name = "standalone-pkg"

    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"
""")
WORKSPACE_TOML = dedent("""\
    [project]
    name = "my-workspace"

    [tool.uv.workspace]
    members = ["packages/*"]
""")


def _build_scaffold_tree(
    root: Path,
    name: str = "test-pkg",
    *,
    hello: bool = False,
    utils: bool = False,
) -> list[str]:
    """Create a minimal scaffolded project tree on disk and return file list.

    This simulates what Copier would produce so that tests can assert
    on the file tree without invoking the real adapter.
    """
    pkg = name.replace("-", "_")
    src = root / "src" / pkg
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(_fake_init_py(has_hello=hello))
    (src / "core").mkdir()
    (src / "core" / "__init__.py").write_text("")

    if utils:
        (src / "utils").mkdir()
        (src / "utils" / "__init__.py").write_text("")

    (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
    (root / "README.md").write_text(f"# {name}\n\nA test project.\n")
    (root / "tests").mkdir()
    (root / "tests" / "__init__.py").write_text("")

    # docs
    docs = root / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(f"# {name}\n\nWelcome to {name}.\n")
    tutorials = docs / "tutorials"
    tutorials.mkdir()
    (tutorials / "getting-started.md").write_text(f"# Getting started with {name}\n")

    # Collect relative file paths
    return [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]


def _fake_init_py(*, has_hello: bool = False) -> str:
    """Return a realistic __init__.py content."""
    version_block = (
        "try:\n"
        "    from ._version import __version__\n"
        "except ImportError:\n"
        '    __version__ = "0.0.0"\n'
    )
    lines = [version_block]
    if has_hello:
        lines.append("def hello() -> str:\n    return 'hello'\n")
    return "\n".join(lines)


def _make_result(
    project_path: Path,
    *,
    passed: bool = True,
    score: int = 100,
) -> ProjectResult:
    """Build a minimal ProjectResult for formatter tests."""
    checks = [
        CheckResult(
            name="test.check",
            category="test",
            passed=passed,
            weight=10,
            message="ok" if passed else "missing",
            details=[] if passed else ["detail line"],
            fix="" if passed else "Run fix command",
        ),
    ]
    return ProjectResult.from_checks(project_path, checks)


def _make_workspace(tmp_path: Path, root_toml: str, member_toml: str = "") -> Path:
    """Create a workspace layout and return the member path.

    Layout:
        tmp_path/pyproject.toml          <- workspace root (with [tool.uv.workspace])
        tmp_path/packages/pkg/pyproject.toml  <- member
    """
    _write_toml(
        tmp_path / "pyproject.toml",
        root_toml,
    )
    member = tmp_path / "packages" / "pkg"
    member.mkdir(parents=True, exist_ok=True)
    if member_toml:
        _write_toml(member / "pyproject.toml", member_toml)
    else:
        # Minimal member pyproject with no tool sections
        _write_toml(
            member / "pyproject.toml",
            """\
            [project]
            name = "pkg"
            version = "0.1.0"
            """,
        )
    return member


def _write_toml(path: Path, content: str) -> None:
    """Write a TOML file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))
