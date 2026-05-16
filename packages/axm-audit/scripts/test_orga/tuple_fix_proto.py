"""Deterministic test-suite auto-fixer — CLI entry point.

This file is a thin shim around the ``fix_proto`` package (12 modules
arranged by hexagonal layer; see ``fix_proto/__init__.py``). All
implementation lives there; this module only handles argparse and
invocation, preserving the legacy ``python tuple_fix_proto.py <path>``
interface.

Pipeline (5 stages + 1 polish, all deterministic; NO_PACKAGE_SYMBOL is
reported but left to a human/agent — its verdict is context-dependent):

    0.5 NON-CANONICAL-RELOCATE  tests/functional/*  → tests/integration/
    0.  FLATTEN                 heterogeneous Test* classes → top-level funcs
    1.  RELOCATE                PYRAMID_LEVEL mismatch → git mv across tiers
    1.5 FLATTEN_LAYOUT          tests/<tier>/<subdir>/ → flat layout
    2.  SPLIT                   FILE_NAMING verdict=SPLIT     anvil moves
    3.  COLLIDE / MERGE         FILE_NAMING verdict=COLLIDE   anvil moves
    4.  RENAME                  FILE_NAMING verdict=NAME_MISMATCH  git mv

The chain re-audits between stages so SPLIT/MERGE/RENAME act on
post-RELOCATE paths, and the whole pipeline runs in a fixed-point loop
(``MAX_ITERATIONS=6``) since each mutation can expose new findings.

Usage::

    uv run --python 3.12 python tuple_fix_proto.py /tmp/proto-fix/axm-audit-copy
    uv run --python 3.12 python tuple_fix_proto.py <path> --apply
    uv run --python 3.12 python tuple_fix_proto.py <path> --rules=TEST_QUALITY_FILE_NAMING

The script defaults to ``--dry-run``. Pass ``--apply`` to actually mutate.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fix_proto import format_report, run

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
