#!/usr/bin/env python3
"""Regenerate a fix-corpus case's ``expected/`` tree from its ``input/`` tree.

Usage::

    uv run python tests/fixtures/fix_corpus/regenerate.py <case_name>
    uv run python tests/fixtures/fix_corpus/regenerate.py --all

For each named case, this script:
1. Copies ``<case>/input/`` to a fresh temp dir.
2. Initialises a git repo (``axm-audit fix`` requires one).
3. Runs ``axm-audit fix --apply`` against the temp dir.
4. Overwrites ``<case>/expected/`` with the post-fix tree.

The script is **destructive**: it deletes the prior ``expected/`` before
copying. Commit the corpus before running so you can diff and review.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CORPUS_ROOT = Path(__file__).parent
CASE_NAMES = (
    "relocate_only",
    "split_only",
    "merge_only",
    "rename_only",
    "flatten_only",
    "mixed",
)


def regenerate_case(name: str) -> None:
    case_dir = CORPUS_ROOT / name
    input_dir = case_dir / "input"
    expected_dir = case_dir / "expected"
    if not input_dir.is_dir():
        raise FileNotFoundError(f"{name}: no input/ tree at {input_dir}")

    with tempfile.TemporaryDirectory(prefix=f"regen_{name}_") as tmp:
        tmp_pkg = Path(tmp) / name
        shutil.copytree(input_dir, tmp_pkg)
        subprocess.run(
            ["git", "init", "--quiet"], cwd=tmp_pkg, check=True, capture_output=True
        )
        result = subprocess.run(
            ["axm-audit", "fix", "--apply", str(tmp_pkg)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            sys.stderr.write(
                f"axm-audit fix failed for {name}:\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}\n"
            )
            raise SystemExit(1)

        if expected_dir.exists():
            shutil.rmtree(expected_dir)
        shutil.copytree(tmp_pkg, expected_dir, ignore=shutil.ignore_patterns(".git"))
    print(f"regenerated {name}/expected/")  # noqa: T201


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("case", nargs="?", help="case name to regenerate")
    group.add_argument(
        "--all", action="store_true", help="regenerate every case in the corpus"
    )
    args = parser.parse_args()

    names = CASE_NAMES if args.all else (args.case,)
    for name in names:
        if name not in CASE_NAMES:
            sys.stderr.write(f"unknown case {name!r}; valid: {', '.join(CASE_NAMES)}\n")
            raise SystemExit(2)
        regenerate_case(name)


if __name__ == "__main__":
    main()
