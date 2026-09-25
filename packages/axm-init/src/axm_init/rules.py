"""Public rule primitives; domain findings do not imply project quality scores."""

from collections.abc import Callable, Iterable
from pathlib import Path

from axm_init.checks._utils import TomlTable, requires_toml, section
from axm_init.models.check import CheckResult

__all__ = ["CheckResult", "TomlTable", "requires_toml", "run_rules", "section"]


def run_rules[T](path: Path, rules: Iterable[Callable[[Path], T]]) -> list[T]:
    """Run explicit rules in order, preserving findings and propagating errors.

    No discovery, score aggregation, exclusions, or domain interpretation is
    performed. Callers own their finding types and presentation policy.
    """
    return [rule(path) for rule in rules]
