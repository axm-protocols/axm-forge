"""Split from ``test_shared_helpers_io.py``."""

import textwrap
from pathlib import Path

from axm_audit.core.rules.test_quality._shared import collect_pkg_public_symbols


def test_collect_pkg_public_symbols_functions_classes_vars(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "mod.py").write_text(
        textwrap.dedent("""
        def f():
            pass

        class C:
            pass

        X = 1
    """)
    )
    symbols = collect_pkg_public_symbols(tmp_path)
    assert {"f", "C", "X"}.issubset(set(symbols))
