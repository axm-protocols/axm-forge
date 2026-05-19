"""Test-quality rules — analyses for pyramid level, tautologies, mocks, etc.

This subpackage houses rules that operate on the ``tests/`` tree rather than
``src/``.  ``_shared`` exposes the AST-based primitives reused by every rule
in this package.
"""

from __future__ import annotations

from axm_audit.core.rules.test_quality import (  # noqa: F401  (side-effect: registration)
    duplicate_tests,
    file_naming,
    no_package_symbol,
    private_imports,
    pyramid_level,
    tautology,
)
from axm_audit.core.rules.test_quality.file_naming import compute_canonical_name

__all__: list[str] = ["compute_canonical_name"]
