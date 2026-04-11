"""CLI entry point for axm-smelt."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import cyclopts

from axm_smelt._version import __version__

app = cyclopts.App(
    name="axm-smelt", help="Deterministic token compaction for LLM inputs."
)


def _read_input(file: Path | None = None) -> str:
    """Read input from *file* or stdin."""
    if file is not None:
        try:
            return file.read_text()
        except FileNotFoundError:
            print(f"Error: No such file: {file}", file=sys.stderr)
            raise SystemExit(1) from None
    return sys.stdin.read()


@app.command
def version() -> None:
    """Show the version."""
    print(__version__)


@app.command
def count(
    *,
    file: Annotated[Path | None, cyclopts.Parameter(name="--file")] = None,
    model: Annotated[str, cyclopts.Parameter(name="--model")] = "o200k_base",
) -> None:
    """Count tokens in input."""
    from axm_smelt.core.counter import count as _count

    text = _read_input(file)
    print(_count(text, model=model))


@app.command
def compact(
    *,
    file: Annotated[Path | None, cyclopts.Parameter(name="--file")] = None,
    strategies: Annotated[str | None, cyclopts.Parameter(name="--strategies")] = None,
    preset: Annotated[str | None, cyclopts.Parameter(name="--preset")] = None,
    output: Annotated[Path | None, cyclopts.Parameter(name="--output")] = None,
) -> None:
    """Compact input and print the result."""
    from axm_smelt.core.pipeline import smelt

    text = _read_input(file)
    strat_list = strategies.split(",") if strategies else None
    try:
        report = smelt(text, strategies=strat_list, preset=preset)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    compacted = report.compacted

    if output is not None:
        output.write_text(compacted)
    else:
        print(compacted)

    print(
        f"Tokens: {report.original_tokens} -> {report.compacted_tokens}"
        f" ({report.savings_pct:.1f}% saved)",
        file=sys.stderr,
    )


@app.command
def check(
    *,
    file: Annotated[Path | None, cyclopts.Parameter(name="--file")] = None,
) -> None:
    """Analyze input without transforming it."""
    from axm_smelt.core.pipeline import check as _check

    text = _read_input(file)
    try:
        report = _check(text)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    lines = [
        f"Format: {report.format.value}",
        f"Tokens: {report.original_tokens}",
        f"Strategies applied: {', '.join(report.strategies_applied) or 'none'}",
    ]
    if report.strategy_estimates:
        lines.append("Strategy estimates:")
        for strat, pct in report.strategy_estimates.items():
            lines.append(f"  {strat}: {pct:.1f}%")
    print("\n".join(lines))


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
