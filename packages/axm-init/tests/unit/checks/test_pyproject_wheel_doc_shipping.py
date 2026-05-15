"""Unit tests for ``check_pyproject_wheel_doc_shipping`` (AXM-1715).

Isolated in a dedicated module to avoid blind appends to the large
existing ``test_pyproject.py``. Mirror rule remains satisfied because
the check lives in ``checks/pyproject.py`` and at least one test module
(``test_pyproject.py``) already mirrors it.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from axm_init.checks.pyproject import check_pyproject_wheel_doc_shipping


def _write_pyproject(project: Path, toml: str) -> None:
    (project / "pyproject.toml").write_text(textwrap.dedent(toml).lstrip())


def test_wheel_doc_shipping_passes_when_explicit_files_are_force_included(
    tmp_path: Path,
) -> None:
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "pkg"

        [tool.axm-init.wheel-doc]
        files = ["docs/x.md"]

        [tool.hatch.build.targets.wheel]
        packages = ["src/pkg"]

        [tool.hatch.build.targets.wheel.force-include]
        "docs/x.md" = "pkg/docs/x.md"
        """,
    )

    result = check_pyproject_wheel_doc_shipping(tmp_path)

    assert result.passed is True
    assert result.weight == 2


def test_wheel_doc_shipping_fails_when_force_include_missing(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "pkg"

        [tool.axm-init.wheel-doc]
        files = ["docs/x.md"]

        [tool.hatch.build.targets.wheel]
        packages = ["src/pkg"]
        """,
    )

    result = check_pyproject_wheel_doc_shipping(tmp_path)

    assert result.passed is False
    assert any("docs/x.md" in d for d in result.details)
    assert "force-include" in result.fix or "force_include" in result.fix


def test_wheel_doc_shipping_autodetects_unfiled_docs(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "pkg"

        [tool.hatch.build.targets.wheel]
        packages = ["src/pkg"]
        """,
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "foo.md").write_text("# foo\n")

    result = check_pyproject_wheel_doc_shipping(tmp_path)

    assert result.passed is False
    assert any("foo.md" in d for d in result.details)


def test_wheel_doc_shipping_passes_when_no_docs_dir(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "pkg"

        [tool.hatch.build.targets.wheel]
        packages = ["src/pkg"]
        """,
    )

    result = check_pyproject_wheel_doc_shipping(tmp_path)

    assert result.passed is True


def test_wheel_doc_shipping_returns_canonical_check_metadata(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
        [project]
        name = "pkg"

        [tool.hatch.build.targets.wheel]
        packages = ["src/pkg"]
        """,
    )

    result = check_pyproject_wheel_doc_shipping(tmp_path)

    assert result.name == "pyproject.wheel_doc_shipping"
    assert result.category == "pyproject"
    assert result.weight == 2
