"""Functional tests for analyze_package — public API boundary.

Covers module discovery, package naming, error handling,
directory filtering, and .gitignore support.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast import analyze_package

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ─── Core behavior ─────────────────────────────────────────────────────────


@pytest.mark.functional
class TestAnalyzePackageUnit:
    """Tests for analyze_package() (pure, fixture-only)."""

    def test_discovers_all_modules(self):
        pkg = analyze_package(SAMPLE_PKG)
        assert len(pkg.modules) >= 3

    def test_package_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        assert pkg.name == "sample_pkg"

    def test_package_root(self):
        pkg = analyze_package(SAMPLE_PKG)
        assert pkg.root == SAMPLE_PKG.resolve()

    def test_module_names_populated(self):
        pkg = analyze_package(SAMPLE_PKG)
        assert len(pkg.module_names) >= 3
