"""Unit tests for checker discovery and CLI lazy imports."""

from __future__ import annotations

import sys

from axm_init.core.checker import ALL_CHECKS


class TestCheckDiscovery:
    """Tests for auto-discovery of check modules."""

    def test_check_discovery_finds_all(self) -> None:
        """Auto-discovery finds 49 checks across 8 categories."""
        total = sum(len(fns) for fns in ALL_CHECKS.values())
        assert total == 48
        assert len(ALL_CHECKS) == 8

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
