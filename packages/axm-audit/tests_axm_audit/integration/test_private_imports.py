"""Split from ``test_private_import_detection.py``."""

import inspect
from pathlib import Path

from radon.complexity import cc_visit


def test_check_complexity_within_budget() -> None:
    from axm_audit.core.rules.test_quality import private_imports

    source = Path(inspect.getfile(private_imports)).read_text()
    blocks = cc_visit(source)

    check_block = next(
        b
        for b in blocks
        if getattr(b, "classname", None) == "PrivateImportsRule" and b.name == "check"
    )
    assert check_block.complexity <= 17
