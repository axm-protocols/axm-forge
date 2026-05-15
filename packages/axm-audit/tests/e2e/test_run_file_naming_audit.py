"""End-to-end smoke tests for the new TEST_QUALITY_FILE_NAMING rule via CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.e2e,
    # The CLI is resolved dynamically via shutil.which, so the
    # NO_PACKAGE_SYMBOL heuristic can't statically reconstruct the argv.
    # The test does exercise the package — declare it explicitly.
    pytest.mark.no_package_symbol_ok,
]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AXM_AUDIT_BIN = shutil.which("axm-audit")


def _rule_ids_in(payload: dict[str, object]) -> set[str]:
    """Walk an axm-audit JSON payload and collect rule_id values."""
    ids: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            rid = node.get("rule_id")
            if isinstance(rid, str):
                ids.add(rid)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(payload)
    return ids


def _findings_in(payload: dict[str, object]) -> list[dict[str, object]]:
    """Collect every dict that looks like a finding (has a 'verdict' key)."""
    out: list[dict[str, object]] = []

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            if "verdict" in node:
                out.append(node)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(payload)
    return out


def test_cli_test_quality_includes_new_rule_json() -> None:
    """AC11 — the CLI 'test-quality --json' surfaces the new rule."""
    if _AXM_AUDIT_BIN is None:
        pytest.skip("axm-audit CLI not on PATH")
    # _AXM_AUDIT_BIN is resolved to an absolute path via shutil.which and is
    # not user input — the S603 warning is acknowledged but safe in this
    # controlled-test context.
    proc = subprocess.run(  # noqa: S603
        [_AXM_AUDIT_BIN, "test-quality", "--json", str(_REPO_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), (
        f"unexpected exit {proc.returncode}: {proc.stderr[:400]}"
    )
    payload = json.loads(proc.stdout)
    assert "TEST_QUALITY_FILE_NAMING" in _rule_ids_in(payload)


def test_cli_audit_test_quality_on_synthetic_collision(tmp_path: Path) -> None:
    """AC6 — CLI reports COLLIDE on a synthetic two-file collision project."""
    project = tmp_path / "proj"
    (project / "src" / "mypkg").mkdir(parents=True)
    (project / "src" / "mypkg" / "__init__.py").write_text("class Rule:\n    pass\n")
    (project / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "mypkg"
            version = "0"
            """
        ).strip()
        + "\n"
    )
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "tests" / "integration" / "test_a.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )
    (project / "tests" / "integration" / "test_b.py").write_text(
        "from mypkg import Rule\n\ndef test_y():\n    Rule()\n"
    )

    if _AXM_AUDIT_BIN is None:
        pytest.skip("axm-audit CLI not on PATH")
    # Same controlled-test context as the first subprocess call above.
    proc = subprocess.run(  # noqa: S603
        [_AXM_AUDIT_BIN, "test-quality", "--json", str(project)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), (
        f"unexpected exit {proc.returncode}: {proc.stderr[:400]}"
    )
    payload = json.loads(proc.stdout)
    collides = [f for f in _findings_in(payload) if f.get("verdict") == "COLLIDE"]
    assert collides, "expected at least one COLLIDE finding in CLI output"
    files = {Path(p).name for p in collides[0].get("files", [])}
    assert files == {"test_a.py", "test_b.py"}
