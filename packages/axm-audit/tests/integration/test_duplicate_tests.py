"""Regression gate for AXM-2175: moving Jaccard fns to ``axm_echo``.

The move replaces the local copies of ``statement_set`` /
``jaccard_similarity`` / ``normalize_dump`` in ``duplicate_tests`` with a
direct import from ``axm_echo``. These tests exercise the ``duplicate_tests``
module's bound helpers directly.
"""

from __future__ import annotations

import axm_echo
import pytest

from axm_audit.core.rules.test_quality import duplicate_tests


@pytest.mark.integration
def test_imports_from_echo_not_local() -> None:
    """AC1: duplicate_tests reuses the echo Jaccard fns, not local copies.

    The three structural helpers the rule binds (``statement_set`` /
    ``jaccard_similarity`` / ``normalize_dump``, kept under the module's
    established ``_``-aliased names) are the *exact same objects* exported by
    ``axm_echo`` and defined in the ``axm_echo`` package — proving there is no
    surviving local copy. The module and tests share the ``axm_audit`` package,
    so reading the aliases is a same-package access.
    """
    bindings = {
        "statement_set": duplicate_tests._statement_set,
        "jaccard_similarity": duplicate_tests._jaccard_similarity,
        "normalize_dump": duplicate_tests._normalize_dump,
    }
    for echo_name, bound in bindings.items():
        echo = getattr(axm_echo, echo_name)
        assert bound is echo, f"{echo_name} is not the axm_echo object"
        assert bound.__module__.startswith("axm_echo"), (
            f"{echo_name} resolves to {bound.__module__}, expected an axm_echo module"
        )
