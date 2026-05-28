"""Shared pytest fixtures."""

import subprocess
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def sample_data() -> dict[str, str]:
    """Provide sample test data."""
    return {"key": "value"}


@pytest.fixture
def audit_result() -> Any:
    from axm_audit.models import AuditResult

    return AuditResult.model_validate(
        {
            "project_path": "/tmp/sample",
            "checks": [
                {
                    "rule_id": "ruff",
                    "message": "ok",
                    "category": "lint",
                    "passed": True,
                    "score": 75,
                },
                {
                    "rule_id": "mypy",
                    "message": "ok",
                    "category": "type",
                    "passed": True,
                },
                {
                    "rule_id": "complexity",
                    "message": "1 function above CC budget",
                    "category": "complexity",
                    "passed": False,
                    "text": "1 function above CC budget",
                    "details": {"hotspots": [{"name": "foo", "cc": 15}]},
                },
                {
                    "rule_id": "TEST_PYRAMID",
                    "message": "pyramid mismatch",
                    "category": "testing",
                    "passed": False,
                    "metadata": {
                        "pyramid_mismatches": [
                            {
                                "test": "tests/unit/test_a.py::test_a",
                                "current_dir": "unit",
                                "detected_level": "integration",
                            },
                            {
                                "test": "tests/unit/test_b.py::test_b",
                                "current_dir": "unit",
                                "detected_level": "unit",
                            },
                        ],
                    },
                },
                {
                    "rule_id": "PRIVATE_IMPORTS",
                    "message": "private imports",
                    "category": "testing",
                    "passed": False,
                    "metadata": {
                        "private_import_violations": [
                            {
                                "file": "tests/unit/test_b.py",
                                "line": 5,
                                "symbol": "_helper",
                            }
                        ],
                    },
                },
                {
                    "rule_id": "duplicates",
                    "message": "duplicates found",
                    "category": "testing",
                    "passed": False,
                    "metadata": {
                        "clusters": [
                            {
                                "signal": "shape:0xabc",
                                "members": [
                                    {
                                        "file": "tests/unit/test_a.py",
                                        "line": 1,
                                        "test": "test_a",
                                    },
                                    {
                                        "file": "tests/unit/test_b.py",
                                        "line": 2,
                                        "test": "test_b",
                                    },
                                ],
                            }
                        ]
                    },
                },
                {
                    "rule_id": "tautologies",
                    "message": "tautologies found",
                    "category": "testing",
                    "passed": False,
                    "metadata": {
                        "verdicts": [
                            {
                                "verdict": "TAUTOLOGY",
                                "test": "test_trivial",
                                "file": "tests/unit/test_c.py",
                                "line": 10,
                            }
                        ]
                    },
                },
            ],
        }
    )


@pytest.fixture
def minimal_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    src = pkg / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    return pkg


@pytest.fixture
def pkg_root(tmp_path: Path) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "tests").mkdir()
    return tmp_path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "tests").mkdir()
    return tmp_path


@pytest.fixture()
def toy_project(tmp_path: Path) -> Path:
    """Create a minimal but valid Python project in *tmp_path*.

    Layout::

        tmp_path/
        ├── pyproject.toml
        ├── src/
        │   └── toy/
        │       ├── __init__.py
        │       └── core.py
        └── tests/
            └── test_core.py
    """
    # -- pyproject.toml --------------------------------------------------
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "toy"
            version = "0.1.0"
            requires-python = ">=3.12"

            [tool.ruff]
            line-length = 88
            select = ["E", "F", "I"]

            [tool.mypy]
            strict = true
        """)
    )

    # -- src/toy/ --------------------------------------------------------
    src = tmp_path / "src" / "toy"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(
        textwrap.dedent("""\
            \"\"\"Toy package.\"\"\"

            from __future__ import annotations

            __all__: list[str] = []
        """)
    )
    (src / "core.py").write_text(
        textwrap.dedent("""\
            \"\"\"Core module of toy package.\"\"\"

            from __future__ import annotations


            def greet(name: str) -> str:
                \"\"\"Return a greeting string.\"\"\"
                return f"Hello, {name}!"
        """)
    )

    # -- tests/ ----------------------------------------------------------
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text(
        textwrap.dedent("""\
            \"\"\"Tests for toy.core.\"\"\"

            from __future__ import annotations

            from toy.core import greet


            def test_greet() -> None:
                \"\"\"Greet returns expected string.\"\"\"
                assert greet("World") == "Hello, World!"
        """)
    )

    return tmp_path


@pytest.fixture
def registry():
    import axm_audit.core.rules  # noqa: F401  (fire decorators)
    from axm_audit.core.rules.base import get_registry

    return get_registry()


@pytest.fixture
def make_pkg(tmp_path: Path) -> Callable[..., Path]:
    """Factory: minimal valid project for ``test_quality`` audits.

    Builds ``<tmp>/pkg_N/`` with ``pyproject.toml`` + ``src/<pkg_name>/__init__.py``
    + empty ``tests/``, then writes any extra ``files`` (relative paths).
    Callable multiple times per test; each call returns a fresh project.
    """
    counter = [0]

    def _make(
        files: dict[str, str] | None = None,
        pyproject_extras: str = "",
        pkg_name: str = "mypkg",
    ) -> Path:
        counter[0] += 1
        root = tmp_path / f"pkg_{counter[0]}"
        src = root / "src" / pkg_name
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        pyproject = (
            "[project]\n"
            f'name = "{pkg_name}"\n'
            'version = "0.0.0"\n'
            'requires-python = ">=3.12"\n'
        )
        if pyproject_extras:
            pyproject += "\n" + pyproject_extras
        (root / "pyproject.toml").write_text(pyproject)
        (root / "tests").mkdir()
        for relpath, content in (files or {}).items():
            target = root / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        return root

    return _make


@pytest.fixture
def make_test_pkg(tmp_path: Path) -> Callable[[dict[str, str]], Path]:
    """Build a minimal git-initialised package with the given source files."""

    def _make(sources: dict[str, str]) -> Path:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'
        )
        (pkg / "src").mkdir()
        (pkg / "src" / "pkg").mkdir()
        (pkg / "src" / "pkg" / "__init__.py").write_text("")
        (pkg / "tests").mkdir()
        for rel, content in sources.items():
            f = pkg / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
        subprocess.run(["git", "init", "-q"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=pkg, check=True)  # noqa: S607
        subprocess.run(["git", "config", "user.name", "t"], cwd=pkg, check=True)  # noqa: S607
        subprocess.run(["git", "add", "-A"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
        subprocess.run(
            ["git", "commit", "-q", "-m", "init"],  # noqa: S607
            cwd=pkg,
            check=True,
            capture_output=True,
        )
        return pkg

    return _make
