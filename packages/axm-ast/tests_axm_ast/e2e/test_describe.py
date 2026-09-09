from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[2]


def test_cli_detail_full_rejected():
    """CLI --detail full must produce a clear error and exit 1."""
    proc = subprocess.run(
        [sys.executable, "-m", "axm_ast", "describe", "--detail", "full"],
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0


@pytest.mark.e2e
def test_cli_names_is_shorter_than_summary() -> None:
    """Packaged --detail names succeeds and is shorter than summary (AC4)."""
    command = [
        str(Path(sys.executable).with_name("axm-ast")),
        "describe",
        str(PACKAGE_ROOT),
        "--detail",
    ]

    names = subprocess.run(
        [*command, "names"],
        capture_output=True,
        text=True,
    )
    summary = subprocess.run(
        [*command, "summary"],
        capture_output=True,
        text=True,
    )

    assert names.returncode == 0, names.stderr
    assert summary.returncode == 0, summary.stderr
    assert len(names.stdout) < len(summary.stdout)


@pytest.mark.e2e
@pytest.mark.parametrize(
    "modules", [("documented",), ("plain",), ("documented", "plain")]
)
@pytest.mark.parametrize("json_output", [False, True])
def test_cli_toc_optional_module_docstrings(
    tmp_path: Path, modules: tuple[str, ...], json_output: bool
) -> None:
    """TOC lists every module and preserves text and JSON with optional docs."""
    for name in modules:
        doc = '"""Documented module."""\n' if name == "documented" else ""
        (tmp_path / f"{name}.py").write_text(
            doc + "def answer():\n    return 42\n\nclass Example:\n    pass\n",
            encoding="utf-8",
        )
    command = [
        str(Path(sys.executable).with_name("axm-ast")),
        "describe",
        str(tmp_path),
        "--detail",
        "toc",
    ]
    if json_output:
        command.append("--json")
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    entries = [
        {
            "name": name,
            "function_count": 1,
            "class_count": 1,
            "symbol_count": 2,
            **({"docstring": "Documented module."} if name == "documented" else {}),
        }
        for name in modules
    ]
    if json_output:
        assert (
            result.stdout
            == json.dumps({"modules": entries, "module_count": len(entries)}, indent=2)
            + "\n"
        )
    else:
        assert result.stdout == "".join(
            f"  {name} (2 symbols)"
            + (" — Documented module." if name == "documented" else "")
            + "\n"
            for name in modules
        )
