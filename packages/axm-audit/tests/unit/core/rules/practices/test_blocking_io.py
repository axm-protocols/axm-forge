"""Unit tests for BlockingIORule (pure)."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.practices.blocking_io import BlockingIORule


class TestBlockingIORuleUnit:
    """Tests for BlockingIORule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_BLOCKING_IO."""
        rule = BlockingIORule()
        assert rule.rule_id == "PRACTICE_BLOCKING_IO"


def _write_src(tmp_path: Path, source: str) -> Path:
    """Write *source* into a minimal ``src/`` package and return the project root."""
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(source)
    return tmp_path


def _async_sleep_violations(
    details: dict[str, object],
) -> list[dict[str, object]]:
    """Extract the time.sleep-in-async violations from a check result's details."""
    violations = details.get("violations", [])
    assert isinstance(violations, list)
    return [v for v in violations if v.get("issue") == "time.sleep in async"]


def test_async_sleep_in_nested_sync_def_not_flagged(tmp_path: Path) -> None:
    """AC1: time.sleep inside a nested sync def within an async def is not flagged."""
    source = (
        "import time\n\n\n"
        "async def f():\n"
        "    def g():\n"
        "        time.sleep(1)\n"
        "    return g\n"
    )
    result = BlockingIORule().check(_write_src(tmp_path, source))
    assert _async_sleep_violations(result.details) == []


def test_async_sleep_direct_flagged_once(tmp_path: Path) -> None:
    """AC2: time.sleep directly in an async def body is flagged exactly once."""
    source = "import time\n\n\nasync def f():\n    time.sleep(1)\n"
    result = BlockingIORule().check(_write_src(tmp_path, source))
    assert len(_async_sleep_violations(result.details)) == 1


def test_nested_async_sleep_not_double_counted(tmp_path: Path) -> None:
    """AC2: an inner async def's sleep is counted once (no duplicate (file, line))."""
    source = (
        "import time\n\n\n"
        "async def outer():\n"
        "    async def inner():\n"
        "        time.sleep(1)\n"
        "    return inner\n"
    )
    result = BlockingIORule().check(_write_src(tmp_path, source))
    violations = _async_sleep_violations(result.details)
    keys = [(v["file"], v["line"]) for v in violations]
    assert len(keys) == len(set(keys))
    assert len(violations) == 1


def test_bare_imported_sleep_in_async_flagged(tmp_path: Path) -> None:
    """AC3: bare sleep() via `from time import sleep` inside async def is flagged."""
    source = "from time import sleep\n\n\nasync def f():\n    sleep(1)\n"
    result = BlockingIORule().check(_write_src(tmp_path, source))
    assert len(_async_sleep_violations(result.details)) == 1


def test_aliased_imported_sleep_in_async_flagged(tmp_path: Path) -> None:
    """AC3: aliased sleep via `from time import sleep as s` in async def is flagged."""
    source = "from time import sleep as s\n\n\nasync def f():\n    s(1)\n"
    result = BlockingIORule().check(_write_src(tmp_path, source))
    assert len(_async_sleep_violations(result.details)) == 1


def test_bare_sleep_in_nested_sync_def_not_flagged(tmp_path: Path) -> None:
    """AC4: bare sleep() via import in a nested sync def within async is not flagged."""
    source = (
        "from time import sleep\n\n\n"
        "async def f():\n"
        "    def g():\n"
        "        sleep(1)\n"
        "    return g\n"
    )
    result = BlockingIORule().check(_write_src(tmp_path, source))
    assert _async_sleep_violations(result.details) == []


def test_blocking_io_rule_registered(registry: dict[str, list[type]]) -> None:
    """BlockingIORule must be registered in the practices bucket."""
    bucket = registry["practices"]
    names = {cls.__name__ for cls in bucket}
    assert "BlockingIORule" in names
