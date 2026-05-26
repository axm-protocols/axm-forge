from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration


def test_move_atomic_batch_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("from __future__ import annotations\n\nclass Foo:\n    pass\n")
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    calls: list[dict[str, Any]] = []

    def spy_batch_edit(*args: Any, **kwargs: Any) -> None:
        calls.append({"args": args, "kwargs": kwargs})
        ops = kwargs.get("operations") or (args[1] if len(args) > 1 else [])
        root = kwargs.get("path") or (args[0] if args else ".")
        for op in ops:
            if op.get("op") == "replace":
                full = Path(root) / op["file"]
                text = full.read_text()
                for e in op.get("edits", []):
                    text = text.replace(e["old"], e["new"])
                full.write_text(text)
            elif op.get("op") == "write":
                full = Path(root) / op["file"]
                full.write_text(op["content"])

    monkeypatch.setattr("axm_anvil.core.move.batch_edit", spy_batch_edit, raising=False)

    move_symbols(src, tgt, ["Foo"], dry_run=False)
    assert len(calls) == 1
    ops = calls[0]["kwargs"].get("operations") or calls[0]["args"][1]
    files = {op["file"] for op in ops}
    assert len(files) == 2
