"""Deterministic test-suite auto-fixer — legacy CLI shim.

The implementation has moved to :mod:`axm_audit.core.fix`. This file is
preserved so existing `/fix-proto` skill invocations continue to work::

    uv run --python 3.12 python tuple_fix_proto.py <path>
    uv run --python 3.12 python tuple_fix_proto.py <path> --apply
    uv run --python 3.12 python tuple_fix_proto.py <path> --rules=TEST_QUALITY_FILE_NAMING

Defaults to ``--dry-run``. Pass ``--apply`` to actually mutate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from axm_audit.core.fix import format_report, run

__all__ = ["main"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("project_path", type=Path, help="Path to package root")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Mutate the project (default: dry-run)",
    )
    parser.add_argument(
        "--rules",
        default="TEST_QUALITY_PYRAMID_LEVEL,TEST_QUALITY_FILE_NAMING",
        help="Comma-separated rule_ids to fix",
    )
    args = parser.parse_args()

    project_path: Path = args.project_path.resolve()
    if not project_path.exists():
        print(f"error: {project_path} does not exist", file=sys.stderr)
        return 2

    rules = {r.strip() for r in args.rules.split(",") if r.strip()}
    report = run(project_path, apply=args.apply, rules=rules)
    print(format_report(report, project_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
