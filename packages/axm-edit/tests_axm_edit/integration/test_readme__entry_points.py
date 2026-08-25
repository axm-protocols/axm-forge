"""Coherence between declared ``axm.tools`` entry points and ``README.md``.

Integration level: reads the package's real ``pyproject.toml`` and
``README.md`` from disk (no hard-coded tool list).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = PACKAGE_ROOT / "pyproject.toml"
README_PATH = PACKAGE_ROOT / "README.md"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_NO_WRITE_RE = re.compile(
    r"aucune\s+[ée]criture"
    r"|n'[ée]crit"
    r"|ne\s+modifie\s+aucun\s+fichier"
    r"|does\s+not\s+write"
    r"|never\s+writes"
    r"|no\s+(disk\s+)?write",
    re.IGNORECASE,
)


def _entry_point_names() -> list[str]:
    """Return the tool names declared under ``[project.entry-points.axm.tools]``."""
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    return sorted(data["project"]["entry-points"]["axm.tools"])


def _readme_text() -> str:
    return README_PATH.read_text(encoding="utf-8")


def _section_body(text: str, needle: str) -> str | None:
    """Return the markdown body of the first heading containing ``needle``."""
    lines = text.splitlines()
    start: int | None = None
    level = 0
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if match is None:
            continue
        if start is None:
            if needle in match.group(2):
                start = index + 1
                level = len(match.group(1))
            continue
        if len(match.group(1)) <= level:
            return "\n".join(lines[start:index])
    if start is None:
        return None
    return "\n".join(lines[start:])


@pytest.mark.parametrize("entry_point", _entry_point_names())
def test_entry_point_is_documented_in_readme(entry_point: str) -> None:
    """AC1: every declared ``axm.tools`` entry point appears in the README."""
    assert entry_point in _readme_text(), (
        f"entry point {entry_point!r} is declared in pyproject.toml "
        "but absent from README.md"
    )


def test_readme_shows_batch_edit_check_call_example() -> None:
    """AC2: the ``batch_edit_check`` section ships a JSON call example."""
    section = _section_body(_readme_text(), "batch_edit_check")
    assert section is not None, "README.md has no `batch_edit_check` section"
    fences = _FENCE_RE.findall(section)
    assert any("path" in fence and "operations" in fence for fence in fences), (
        "no code fence with both `path` and `operations` under `batch_edit_check`"
    )


def test_readme_documents_batch_edit_check_read_only_contract() -> None:
    """AC3: the section states the read-only, no-disk-write contract."""
    section = _section_body(_readme_text(), "batch_edit_check")
    assert section is not None, "README.md has no `batch_edit_check` section"
    assert "read-only" in section.lower(), (
        "the `batch_edit_check` section never mentions `read-only`"
    )
    assert _NO_WRITE_RE.search(section) is not None, (
        "the `batch_edit_check` section never states that no disk write occurs"
    )


def test_readme_documents_the_rewrite_operation() -> None:
    """AC7: the README documents the rewrite op, its keys and the closed create."""
    text = _readme_text()

    assert "rewrite" in text.lower(), "README.md never mentions the rewrite operation"
    documented = [
        fence
        for fence in _FENCE_RE.findall(text)
        if "rewrite" in fence
        and all(key in fence for key in ("file", "content", "expected_checksum"))
    ]
    assert documented, (
        "no code fence documents the rewrite op with its three required keys "
        "(file, content, expected_checksum)"
    )
    assert re.search(r"sha256", text, re.IGNORECASE) is not None, (
        "the README never states that expected_checksum is the sha256 digest "
        "of the current bytes"
    )
    assert re.search(r"overwrite", text, re.IGNORECASE) is not None, (
        "the README never states that a create on an existing target stays "
        "fail-closed, with no overwrite flag"
    )
