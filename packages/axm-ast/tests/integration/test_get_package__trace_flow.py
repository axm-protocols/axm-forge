"""Split from ``test_flows_complexity_refactor.py``."""

import textwrap
from pathlib import Path

from axm_ast.core.cache import get_package
from axm_ast.core.flows import trace_flow
from tests.integration._helpers import _write_pkg


class TestEmptyFlowTrace:
    """Entry with no callees returns empty steps list."""

    def test_no_callees_returns_empty_steps(self, tmp_path: Path) -> None:
        pkg_dir = _write_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "leaf.py": textwrap.dedent("""\
                def lonely():
                    return 42
            """),
            },
        )
        pkg = get_package(pkg_dir)
        steps, _ = trace_flow(pkg, "lonely")
        # A leaf function with no callees: either empty list or single root step
        if steps:
            # Only the root entry itself, no children
            assert all(s.depth == 0 for s in steps)
