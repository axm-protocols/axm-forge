"""CLI entry point for axm-anvil."""

from __future__ import annotations

import sys
from typing import Annotated, Literal

import cyclopts

from axm_anvil.tools.move import MoveTool

__all__ = ["app"]


app = cyclopts.App(
    name="axm-anvil",
    help="Deterministic CST-based refactoring toolkit for Python.",
)


@app.command
def move(  # noqa: PLR0913
    from_file: Annotated[
        str,
        cyclopts.Parameter(help="Source Python file path."),
    ],
    to_file: Annotated[
        str,
        cyclopts.Parameter(help="Target Python file path."),
    ],
    symbols: Annotated[
        str,
        cyclopts.Parameter(help="Comma-separated symbol names to move."),
    ],
    *,
    dry_run: Annotated[
        bool,
        cyclopts.Parameter(name=["--dry-run"], help="Preview without writing."),
    ] = False,
    path: Annotated[
        str,
        cyclopts.Parameter(name=["--path"], help="Workspace root."),
    ] = ".",
    shared_helpers: Annotated[
        Literal["duplicate", "error"],
        cyclopts.Parameter(
            name=["--shared-helpers"],
            help="Strategy for helpers used by both moved and remaining symbols.",
        ),
    ] = "duplicate",
    reexport: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--reexport"],
            help="Leave callers untouched; inject a re-export in the source module.",
        ),
    ] = False,
    rename: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--rename"],
            help='JSON object mapping old to new names, e.g. \'{"Old": "New"}\'.',
        ),
    ] = None,
    check: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--check"],
            help="Simulate the move (incl. cycle detection) without writing.",
        ),
    ] = False,
    strict: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--strict"],
            help="Fail on an absent symbol instead of skipping it with a warning.",
        ),
    ] = False,
    insert_after: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--insert-after"],
            help="Place moved blocks after this target top-level symbol.",
        ),
    ] = None,
    include_helpers: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--include-helpers"],
            help="Copy transitively-referenced local helpers/constants into "
            "the target (default). Use --no-include-helpers to skip them.",
        ),
    ] = True,
    side_effect_decorators: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--side-effect-decorators"],
            help="Comma-separated extra side-effect decorator dotted-names "
            "that extend the built-in whitelist (e.g. 'mylib.register').",
        ),
    ] = None,
) -> None:
    """Move top-level symbols between Python files atomically."""
    result = MoveTool().execute(
        path=path,
        symbols=symbols,
        from_file=from_file,
        to_file=to_file,
        dry_run=dry_run,
        shared_helpers=shared_helpers,
        reexport=reexport,
        rename=rename,
        check=check,
        strict=strict,
        insert_after=insert_after,
        include_helpers=include_helpers,
        side_effect_decorators=side_effect_decorators,
    )
    if not result.success:
        print(result.error or "move failed", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)
    if result.text:
        print(result.text)  # noqa: T201
