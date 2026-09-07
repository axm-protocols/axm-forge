"""Integration coverage for write-tool keyed locking."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from axm.tools.base import ToolResult

from axm_mcp import wrapping
from axm_mcp.wrapping import build_wrappers


class _ObservedWriter:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self._state_lock = threading.Lock()

    def execute(self, *, path: str, **_kwargs: Any) -> ToolResult:
        with self._state_lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        try:
            with Path(path).open("a", encoding="utf-8") as stream:
                stream.write("entry\n")
                stream.flush()
                time.sleep(0.05)
        finally:
            with self._state_lock:
                self.active -= 1
        return ToolResult(success=True, data={}, text="ok")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_writes_to_same_real_file_do_not_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: concurrent wrapped writes to one real file execute serially."""
    target = tmp_path / "shared.txt"
    writer = _ObservedWriter()
    monkeypatch.setattr(wrapping, "_HTTP_MODE", True)
    _, wrapped = build_wrappers(
        "write_file",
        writer,
        write_contract_resolver=lambda: None,
    )

    await asyncio.gather(
        wrapped(path=str(target)),
        wrapped(path=str(target)),
    )

    assert writer.maximum_active == 1
    assert target.read_text(encoding="utf-8").splitlines() == ["entry", "entry"]
