"""Pyramid classifier credits inline ``python -c \"<first-party>\"`` as e2e.

Regression guard for the blind spot shared with
``TEST_QUALITY_NO_PACKAGE_SYMBOL``: a black-box e2e test that drives the
package via ``subprocess.run([sys.executable, \"-c\", script, ...])`` where the
inline ``script`` imports a first-party package must classify as ``e2e``, not
``integration`` -- even when the package declares no ``[project.scripts]``.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.pyramid_level import scan_test_file

pytestmark = pytest.mark.integration


def _scan_one(tmp_path: Path, src: str, pkg_prefixes: set[str]) -> object:
    """Write *src* into a scriptless package and classify its single test."""
    pkg_root = tmp_path
    tests_dir = pkg_root / "tests" / "e2e"
    tests_dir.mkdir(parents=True)
    test_file = tests_dir / "test_overfit.py"
    test_file.write_text(textwrap.dedent(src).lstrip())
    tree = ast.parse(test_file.read_text())
    findings = scan_test_file(test_file, tree, pkg_root, pkg_prefixes, None, tests_dir)
    assert len(findings) == 1
    return findings[0]


def test_inline_python_c_first_party_classifies_e2e(tmp_path: Path) -> None:
    """Inline ``python -c`` importing a first-party pkg -> e2e (no scripts)."""
    src = """
        import subprocess
        import sys
        import textwrap

        import pytest

        pytestmark = [pytest.mark.e2e]

        def test_x(tmp_path):
            script = textwrap.dedent('''
                from axm_train.core.lora import train_lora
                train_lora()
            ''')
            subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=False)
    """
    finding = _scan_one(tmp_path, src, {"axm_train"})
    assert finding.level == "e2e"
    assert finding.has_subprocess is True
    assert "subprocess" in finding.reason


def test_inline_python_c_no_first_party_not_promoted(tmp_path: Path) -> None:
    """Inline ``python -c`` importing nothing first-party stays non-e2e."""
    src = """
        import subprocess
        import sys
        import textwrap

        import pytest

        pytestmark = [pytest.mark.e2e]

        def test_x(tmp_path):
            script = textwrap.dedent('''
                import json
                print(json.dumps({}))
            ''')
            subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=False)
    """
    finding = _scan_one(tmp_path, src, {"axm_train"})
    assert finding.level != "e2e"
