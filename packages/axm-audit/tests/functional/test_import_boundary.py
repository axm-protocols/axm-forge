from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.architecture import ImportBoundaryRule

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_package(src: Path, name: str, files: dict[str, str] | None = None) -> Path:
    """Create a package under *src* with ``__init__.py`` and optional files."""
    pkg = src / name
    pkg.mkdir(parents=True, exist_ok=True)
    init = pkg / "__init__.py"
    if not init.exists():
        init.write_text("")
    for fname, content in (files or {}).items():
        fpath = pkg / fname
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content)
    return pkg


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


@pytest.mark.functional
class TestImportBoundaryCleanProject:
    """Project with only root-level cross imports passes."""

    def test_clean(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_package(src, "pkg_a", {"mod.py": "import pkg_b\n"})
        _make_package(src, "pkg_b", {"mod.py": "import pkg_a\n"})

        result = ImportBoundaryRule().check(tmp_path)
        assert result.passed is True
        assert result.details is not None
        assert result.details["score"] == 100


@pytest.mark.functional
class TestImportBoundaryViolations:
    """Deep cross-package import is flagged."""

    def test_violation_reported(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_package(
            src,
            "pkg_a",
            {"mod.py": "from pkg_b.internal.helper import X\n"},
        )
        _make_package(
            src,
            "pkg_b",
            {
                "internal/__init__.py": "",
                "internal/helper.py": "X = 1\n",
            },
        )

        result = ImportBoundaryRule().check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        violations = result.details["violations"]
        assert len(violations) >= 1
        v = violations[0]
        assert "pkg_b.internal.helper" in v["import"]
        assert "line" in v
        assert "file" in v


@pytest.mark.functional
class TestImportBoundaryWithAllowList:
    """Allowed deep import is excluded from violations."""

    def test_allow_list_suppresses(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_package(
            src,
            "pkg_a",
            {"mod.py": "from pkg_b.internal.helper import X\n"},
        )
        _make_package(
            src,
            "pkg_b",
            {
                "internal/__init__.py": "",
                "internal/helper.py": "X = 1\n",
            },
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.axm-audit.import-boundary]\nallow = ["pkg_b.internal.helper"]\n'
        )

        result = ImportBoundaryRule().check(tmp_path)
        assert result.passed is True


@pytest.mark.functional
class TestImportBoundaryMonorepo:
    """Only cross-package deep imports are flagged, not intra-package."""

    def test_monorepo_boundaries(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_package(
            src,
            "pkg_a",
            {
                "core/__init__.py": "",
                "core/mod.py": (
                    "from pkg_a.core import stuff\nfrom pkg_b.internal import helper\n"
                ),
                "core/stuff.py": "val = 1\n",
            },
        )
        _make_package(
            src,
            "pkg_b",
            {
                "internal/__init__.py": "",
                "internal/helper.py": "X = 1\n",
            },
        )
        _make_package(src, "pkg_c")

        result = ImportBoundaryRule().check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        violations = result.details["violations"]
        imports = [v["import"] for v in violations]
        assert any("pkg_b.internal" in i for i in imports)
        assert not any("pkg_a.core" in i for i in imports)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.functional
class TestImportBoundaryEdgeCases:
    """Boundary conditions for ImportBoundaryRule."""

    def test_no_src_directory(self, tmp_path: Path) -> None:
        """Project without src/ returns passed via check_src() early return."""
        result = ImportBoundaryRule().check(tmp_path)
        assert result.passed is True

    def test_only_future_imports(self, tmp_path: Path) -> None:
        """__future__ imports produce no violations."""
        src = tmp_path / "src"
        _make_package(src, "pkg_a", {"mod.py": "from __future__ import annotations\n"})
        _make_package(src, "pkg_b")

        result = ImportBoundaryRule().check(tmp_path)
        assert result.passed is True

    def test_reexport_in_init(self, tmp_path: Path) -> None:
        """Importing from package root (re-export) is not a violation."""
        src = tmp_path / "src"
        _make_package(
            src,
            "pkg_a",
            {"mod.py": "from pkg_b import X\n"},
        )
        _make_package(
            src,
            "pkg_b",
            {"__init__.py": "from pkg_b.internal import X\n", "internal.py": "X = 1\n"},
        )

        result = ImportBoundaryRule().check(tmp_path)
        assert result.details is not None
        violations = result.details.get("violations", [])
        pkg_a_violations = [v for v in violations if "pkg_a" in v.get("file", "")]
        assert len(pkg_a_violations) == 0

    def test_conditional_import_not_detected(self, tmp_path: Path) -> None:
        """TYPE_CHECKING guard is not top-level — not detected."""
        src = tmp_path / "src"
        _make_package(
            src,
            "pkg_a",
            {
                "mod.py": (
                    "from __future__ import annotations\n"
                    "from typing import TYPE_CHECKING\n"
                    "if TYPE_CHECKING:\n"
                    "    from pkg_b.models import X\n"
                ),
            },
        )
        _make_package(src, "pkg_b", {"models.py": "X = 1\n"})

        result = ImportBoundaryRule().check(tmp_path)
        assert result.passed is True

    def test_self_import(self, tmp_path: Path) -> None:
        """Package importing its own sub-modules is not a violation."""
        src = tmp_path / "src"
        _make_package(
            src,
            "pkg_a",
            {
                "core/__init__.py": "",
                "core/mod.py": "from pkg_a.core import something\n",
                "core/something.py": "val = 1\n",
            },
        )

        result = ImportBoundaryRule().check(tmp_path)
        assert result.passed is True

    def test_deeply_nested_import(self, tmp_path: Path) -> None:
        """Deeply nested import reports full module path."""
        src = tmp_path / "src"
        _make_package(
            src,
            "pkg_a",
            {"mod.py": "from pkg_b.core.db.session import get_session\n"},
        )
        _make_package(
            src,
            "pkg_b",
            {
                "core/__init__.py": "",
                "core/db/__init__.py": "",
                "core/db/session.py": "def get_session(): ...\n",
            },
        )

        result = ImportBoundaryRule().check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        violations = result.details["violations"]
        assert len(violations) == 1
        assert "pkg_b.core.db.session" in violations[0]["import"]
