"""Shared pytest fixtures."""

import textwrap
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
