"""Shared test fixtures for axm-init tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_init.adapters.copier import CopierConfig
from axm_init.models.results import ScaffoldResult
from tests_axm_init.integration._helpers import MKDOCS_FULL, WORKSPACE_TOML

# ── Sample Data ──────────────────────────────────────────────────────────

SAMPLE_PROJECT_NAME = "test-project"
SAMPLE_AUTHOR = "Test Author"
SAMPLE_EMAIL = "test@example.com"
SAMPLE_DESCRIPTION = "A test project"


# ── Post-copy artifacts ──────────────────────────────────────────────────


def materialize_post_copy_artifacts(root: Path) -> None:
    """Recreate the deterministic side-effects of the skipped post-copy tasks.

    The bundled templates declare ``_tasks`` that shell out to ``cp licences/``,
    ``git init``, ``uv python pin`` and two ``uv add`` invocations. Rendering
    with ``skip_tasks=True`` therefore leaves four deterministic artifacts
    absent: ``LICENSE``, ``.python-version``, ``uv.lock`` and the installed
    pre-commit hook. Those four are network-free and cheap, so they are
    synthesized here; only the genuinely network-bound package resolution is
    skipped.

    The point is cost, measured on the ``python-project`` template: running the
    tasks costs 2.23s and 239 MB (72 packages resolved, 72 installed) against
    0.60s and 0.1 MB with them skipped, and a full suite run created 13 virtual
    environments and 110 git repositories for 2.7 GB of temporary state. The
    rendered tree is identical either way, so a test asserting template
    structure or gold-standard compliance keeps a real contract while paying for
    the render alone — never for an installation it does not inspect.
    """
    (root / "LICENSE").write_text("Apache License 2.0\n", encoding="utf-8")
    (root / ".python-version").write_text("3.12\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    hooks = root / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")


@contextmanager
def scaffold_without_tasks() -> Generator[None]:
    """Make every scaffold inside this block render files only.

    ``InitScaffoldTool`` deliberately exposes no ``skip_tasks`` argument — that
    is a test concern, not part of its contract — so the flag is injected by
    swapping the adapter's config factory for the duration of the block. Every
    ``CopierConfig`` the tool builds then carries ``skip_tasks=True``.

    Callers that assert on gold-standard compliance must follow up with
    :func:`materialize_post_copy_artifacts`; callers that only read rendered
    template files need nothing more.
    """
    from axm_init.adapters import copier as copier_module

    real_config = copier_module.CopierConfig

    def _no_tasks(**kwargs: object) -> CopierConfig:
        return real_config(**{**kwargs, "skip_tasks": True})

    with patch.object(copier_module, "CopierConfig", _no_tasks):
        yield


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A temporary directory for project scaffolding."""
    target = tmp_path / "my-project"
    target.mkdir()
    return target


@pytest.fixture
def sample_copier_config(project_dir: Path) -> CopierConfig:
    """A fully populated CopierConfig for testing."""
    return CopierConfig(
        template_path=Path("src/axm_init/templates/python-project"),
        destination=project_dir,
        data={
            "package_name": SAMPLE_PROJECT_NAME,
            "description": SAMPLE_DESCRIPTION,
            "org": "TestOrg",
            "license": "MIT",
            "author_name": SAMPLE_AUTHOR,
            "author_email": SAMPLE_EMAIL,
        },
    )


@pytest.fixture
def sample_scaffold_result() -> ScaffoldResult:
    """A successful ScaffoldResult."""
    return ScaffoldResult(
        success=True,
        path="test-project",
        message="Project scaffolded via Copier",
    )


@pytest.fixture
def failed_scaffold_result() -> ScaffoldResult:
    """A failed ScaffoldResult."""
    return ScaffoldResult(
        success=False,
        path="test-project",
        message="Copier failed: template not found",
    )


@pytest.fixture
def mock_pypi_adapter() -> MagicMock:
    """A mock PyPIAdapter."""
    return MagicMock()


@pytest.fixture()
def gold_project__from_check_engine_run_and_format(tmp_path: Path) -> Path:
    """Minimal gold-standard project for engine tests."""
    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-pkg"\ndynamic = ["version"]\n'
        "classifiers = [\n"
        '    "Development Status :: 3 - Alpha",\n'
        '    "Programming Language :: Python :: 3.12",\n'
        '    "Typing :: Typed",\n]\n'
        "\n[project.urls]\n"
        'Homepage = "https://github.com/org/test-pkg"\n'
        'Documentation = "https://org.github.io/test-pkg/"\n'
        'Repository = "https://github.com/org/test-pkg.git"\n'
        'Issues = "https://github.com/org/test-pkg/issues"\n'
        "\n[build-system]\n"
        'requires = ["hatchling", "hatch-vcs"]\n'
        'build-backend = "hatchling.build"\n'
        "\n[dependency-groups]\n"
        'dev = ["pytest>=8.0","pytest-xdist>=3.8.0","pytest-cov>=4.0","ruff>=0.8","mypy>=1.14","prek>=0.4.4"]\n'  # noqa: E501
        'docs = ["mkdocs-material>=9.0","mkdocstrings[python]>=0.27",'
        '"mkdocs-gen-files>=0.5","mkdocs-literate-nav>=0.6"]\n'
        "\n[tool.mypy]\nstrict = true\npretty = true\n"
        "disallow_incomplete_defs = true\ncheck_untyped_defs = true\n"
        "\n[tool.ruff.lint]\n"
        'select = ["E","F","W","I","UP","B","SIM","S","BLE","PLR","N","RUF"]\n'
        "[tool.ruff.lint.per-file-ignores]\n"
        '"tests/*" = ["S101"]\n'
        "[tool.ruff.lint.isort]\n"
        'known-first-party = ["test_pkg"]\n'
        "\n[tool.pytest.ini_options]\n"
        'addopts = ["--strict-markers","--strict-config","--import-mode=importlib"]\n'
        'pythonpath = ["src"]\nfilterwarnings = ["error"]\n'
        "\n[tool.coverage.run]\nbranch = true\nrelative_files = true\n"
        "[tool.coverage.xml]\n"
        'output = "coverage.xml"\n'
        "[tool.coverage.report]\n"
        'exclude_lines = ["pragma: no cover"]\n'
        '\n[tool.git-cliff.changelog]\nheader = "# Changelog"\n'
    )
    # mkdocs
    (tmp_path / "mkdocs.yml").write_text(
        "nav:\n  - Tutorials:\n    - t.md\n  - How-To Guides:\n    - h.md\n"
        "  - Reference:\n    - r.md\n  - Explanation:\n    - e.md\n"
        "plugins:\n  - gen-files:\n      scripts: [docs/gen_ref_pages.py]\n"
        "  - literate-nav:\n      nav_file: SUMMARY.md\n  - mkdocstrings:\n"
    )
    # pre-commit
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: ruff\n    hooks:\n      - id: ruff\n      - id: ruff-format\n"
        "  - repo: mypy\n    hooks:\n      - id: mypy\n"
        "  - repo: conv\n    hooks:\n      - id: conventional-pre-commit\n"
        "  - repo: basic\n    hooks:\n      - id: trailing-whitespace\n"
        "      - id: end-of-file-fixer\n      - id: check-yaml\n"
    )
    # Makefile
    (tmp_path / "Makefile").write_text(
        ".PHONY: install check test format lint audit clean docs-serve\n"
        "install:\n\techo\ncheck:\n\techo\nlint:\n\techo\nformat:\n\techo\n"
        "test:\n\techo\naudit:\n\techo\nclean:\n\techo\ndocs-serve:\n\techo\n"
    )
    # CI
    ci_dir = tmp_path / ".github" / "workflows"
    ci_dir.mkdir(parents=True)
    (ci_dir / "ci.yml").write_text(
        "jobs:\n  lint:\n    steps:\n      - run: make lint\n"
        "  security:\n    steps:\n      - run: pip-audit\n"
        "  test:\n    strategy:\n      matrix:\n        python-version: ['3.12']\n"
        "    steps:\n      - run: pytest\n"
        "  coverage:\n    steps:\n      - uses: coverallsapp/github-action@v2\n"
    )
    (ci_dir / "publish.yml").write_text(
        "name: Publish\npermissions:\n  id-token: write\n"
    )
    (tmp_path / ".github" / "dependabot.yml").write_text(
        "version: 2\nupdates:\n  - package-ecosystem: pip\n"
    )
    # Files
    (tmp_path / "README.md").write_text(
        "# test-pkg\n\n"
        "[![axm-audit](https://img.shields.io/badge/axm--audit-A-green)](.)\n"
        "[![axm-init](https://img.shields.io/badge/axm--init-A-green)](.)\n\n"
        "**desc**\n\n---\n\n## Features\n\n"
        "## Installation\n\n## Quick Start\n\n## Development\n\n## License\n"
    )
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n")
    (tmp_path / "LICENSE").write_text("MIT\n")
    (tmp_path / "uv.lock").write_text("version = 1\n")
    (tmp_path / ".python-version").write_text("3.12\n")
    pkg = tmp_path / "src" / "test_pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "py.typed").write_text("")
    tests_dir = tmp_path / "tests"
    for sub in ("unit", "integration", "e2e"):
        (tests_dir / sub).mkdir(parents=True)
    (tests_dir / "unit" / "test_x.py").write_text("def test_x() -> None: pass\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "gen_ref_pages.py").write_text("")
    # git hooks
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pre-commit").write_text("#!/bin/sh\n")
    return tmp_path


@pytest.fixture()
def workspace_member(tmp_path: Path) -> Path:
    """Create a workspace member layout: tmp/packages/pkg/ with mkdocs.yml at root."""
    pkg = tmp_path / "packages" / "pkg"
    pkg.mkdir(parents=True)
    (tmp_path / "mkdocs.yml").write_text(MKDOCS_FULL)
    return pkg


@pytest.fixture()
def workspace_root__from_cli_workspace_scaffold_subcommands(tmp_path: Path) -> Path:
    """Create a minimal workspace structure for tests."""
    ws = tmp_path / "test-ws"
    ws.mkdir()
    (ws / "pyproject.toml").write_text(
        '[project]\nname = "test-ws"\n\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    (ws / "Makefile").write_text("test-all:\n\techo test\n")
    (ws / "mkdocs.yml").write_text("site_name: test\nnav:\n  - Home: index.md\n")
    ci_dir = ws / ".github" / "workflows"
    ci_dir.mkdir(parents=True)
    (ci_dir / "ci.yml").write_text(
        "jobs:\n  test:\n    strategy:\n      matrix:\n"
        "        package:\n          - existing\n"
        "    steps:\n      - run: echo test\n"
    )
    (ci_dir / "publish.yml").write_text(
        "name: Publish\non:\n  push:\n"
        "    tags:\n"
        '      - "v*"\n'
        "jobs:\n  pub:\n    runs-on: ubuntu-latest\n"
    )
    (ws / "packages").mkdir()
    return ws


@pytest.fixture()
def workspace_root__from_workspace_context_detection(tmp_path: Path) -> Path:
    """A UV workspace root with two member packages."""
    (tmp_path / "pyproject.toml").write_text(WORKSPACE_TOML)
    for pkg_name in ("pkg-a", "pkg-b"):
        pkg = tmp_path / "packages" / pkg_name
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text(f'[project]\nname = "{pkg_name}"\n')
    return tmp_path


@pytest.fixture()
def ws_root(tmp_path: Path) -> Path:
    """Minimal workspace root with one member under packages/."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    member = tmp_path / "packages" / "pkg-a"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\nrequires-python = ">=3.12"\n'
    )
    (member / "src").mkdir()
    # Suite nommée d'après le membre (tests_<module>) : c'est ce que la règle
    # members_consistent attend, un `tests/` partagé collisionnant entre membres.
    (member / "tests_pkg_a").mkdir()
    return tmp_path
