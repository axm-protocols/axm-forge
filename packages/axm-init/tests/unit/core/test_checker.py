"""Unit tests for checker discovery and CLI lazy imports."""

from __future__ import annotations

import subprocess
import sys
import textwrap

from axm_init.core.checker import ALL_CHECKS


class TestCheckDiscovery:
    """Tests for auto-discovery of check modules."""

    def test_check_discovery_finds_all(self) -> None:
        """Auto-discovery finds 49 checks across 8 categories."""
        total = sum(len(fns) for fns in ALL_CHECKS.values())
        assert total == 49
        assert len(ALL_CHECKS) == 8

    def test_discover_checks_includes_wheel_doc_shipping(self) -> None:
        """Auto-discovery picks up the wheel-doc-shipping check (AXM-1715)."""
        pyproject_fns = ALL_CHECKS.get("pyproject", [])
        names = {fn.__name__ for fn in pyproject_fns}
        assert "check_pyproject_wheel_doc_shipping" in names

    def test_discovery_categories(self) -> None:
        """All expected categories are discovered."""
        expected = {
            "pyproject",
            "ci",
            "tooling",
            "docs",
            "structure",
            "deps",
            "changelog",
            "workspace",
        }
        assert set(ALL_CHECKS.keys()) == expected

    def test_discovery_skips_private_modules(self) -> None:
        """Private modules like _utils are not included."""
        assert "_utils" not in ALL_CHECKS

    def test_workspace_category_discovered(self) -> None:
        """workspace category exists in ALL_CHECKS with the expected 9 checks."""
        assert "workspace" in ALL_CHECKS
        assert len(ALL_CHECKS["workspace"]) == 9


class TestCLILazyImports:
    """Verify CLI adapter imports are lazy."""

    def test_cli_scaffold_lazy(self) -> None:
        """Importing axm_init.cli does not eagerly import adapters/core."""
        # Force reimport by checking that the modules are NOT loaded
        # as a side-effect of importing cli
        lazy_modules = [
            "axm_init.adapters.copier",
            "axm_init.adapters.credentials",
            "axm_init.adapters.pypi",
            "axm_init.core.reserver",
            "axm_init.core.templates",
        ]
        # Remove from cache if present
        cached = {m: sys.modules.pop(m, None) for m in lazy_modules}
        # Also remove cli to force re-evaluation
        original_cli = sys.modules.pop("axm_init.cli", None)
        try:
            import importlib

            importlib.import_module("axm_init.cli")
            for mod in lazy_modules:
                assert mod not in sys.modules, (
                    f"{mod} was eagerly imported by axm_init.cli"
                )
        finally:
            # Restore cache — including CLI itself to avoid breaking
            # @patch("axm_init.cli.X") in subsequent tests
            if original_cli is not None:
                sys.modules["axm_init.cli"] = original_cli
            for m, v in cached.items():
                if v is not None:
                    sys.modules[m] = v


# --- coverage_upload removal regression guards ---


def test_all_checks_no_coverage_upload():
    """After removal, _discover_checks() must not include coverage_upload."""
    from axm_init.checks import ci

    check_names = [
        fn.__name__
        for fn in vars(ci).values()
        if callable(fn) and getattr(fn, "__name__", "").startswith("check_")
    ]
    assert "check_ci_coverage_upload" not in check_names


def test_redirect_for_member_no_coverage_upload():
    """REDIRECT_FOR_MEMBER must not contain ci.ci_coverage_upload after removal."""
    from axm_init.core.checker import REDIRECT_FOR_MEMBER

    assert "ci.ci_coverage_upload" not in REDIRECT_FOR_MEMBER


def test_checker_imports_at_runtime() -> None:
    """Importing checker in a fresh interpreter raises no ImportError."""
    code = textwrap.dedent("""
        from axm_init.core.checker import CheckEngine
        print("OK")
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"ImportError: {result.stderr}"
    assert "OK" in result.stdout


def test_all_checks_registry_populated() -> None:
    """ALL_CHECKS registry is populated with callable check functions."""
    from axm_init.core.checker import ALL_CHECKS

    assert isinstance(ALL_CHECKS, dict)
    assert len(ALL_CHECKS) > 0
    for category, fns in ALL_CHECKS.items():
        assert isinstance(category, str)
        assert all(callable(fn) for fn in fns)
