"""Test-quality rules — analyses for pyramid level, tautologies, mocks, etc.

This subpackage houses rules that operate on the ``tests/`` tree rather than
``src/``.  ``_shared`` exposes the AST-based primitives reused by every rule
in this package.
"""

from __future__ import annotations

from axm_audit.core.rules.test_quality import duplicate_tests as _duplicate_tests
from axm_audit.core.rules.test_quality import private_imports as _private_imports
from axm_audit.core.rules.test_quality import pyramid_level as _pyramid_level
from axm_audit.core.rules.test_quality import tautology as _tautology

__all__: list[str] = []

_ = _duplicate_tests
_ = _private_imports
_ = _pyramid_level
_ = _tautology
