from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.practices import BlockingIORule


def _write_file(base: Path, rel: str, content: str) -> None:
    """Write a file under base, creating parent dirs."""
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


class TestBlockingIOTextRendering:
    """Tests for BlockingIORule.check() text= rendering."""

    def test_text_none_when_passed(self, tmp_path: Path) -> None:
        """Clean async code produces text=None."""
        _write_file(
            tmp_path,
            "src/ok.py",
            "import asyncio\n\nasync def f():\n    await asyncio.sleep(1)\n",
        )
        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.text is None

    def test_text_bullets_sleep_in_async(self, tmp_path: Path) -> None:
        """time.sleep in async def produces bullet line."""
        _write_file(
            tmp_path,
            "src/bad.py",
            "import time\n\nasync def f():\n    time.sleep(1)\n",
        )
        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.text is not None
        assert "     \u2022 bad.py:4: time.sleep in async" in result.text

    def test_text_bullets_no_timeout(self, tmp_path: Path) -> None:
        """HTTP call without timeout produces bullet line."""
        _write_file(
            tmp_path,
            "src/bad.py",
            "import requests\n\ndef f():\n    requests.get('http://example.com')\n",
        )
        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.text is not None
        assert "     \u2022 bad.py:4: HTTP call without timeout" in result.text

    def test_text_multiple_violations(self, tmp_path: Path) -> None:
        """Multiple violations produce multiple bullet lines."""
        _write_file(
            tmp_path,
            "src/bad.py",
            (
                "import time\nimport requests\n\n"
                "async def f():\n    time.sleep(1)\n\n"
                "def g():\n    requests.get('http://x')\n"
            ),
        )
        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.text is not None
        lines = result.text.splitlines()
        assert len(lines) == 2
        assert all(line.startswith("     \u2022") for line in lines)

    def test_empty_src_directory(self, tmp_path: Path) -> None:
        """Empty src/ directory returns text=None and passed=True."""
        (tmp_path / "src").mkdir()
        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.text is None
        assert result.passed is True

    def test_single_violation_no_trailing_newline(self, tmp_path: Path) -> None:
        """Single violation produces single bullet line without trailing newline."""
        _write_file(
            tmp_path,
            "src/bad.py",
            "import time\n\nasync def f():\n    time.sleep(1)\n",
        )
        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.text is not None
        assert not result.text.endswith("\n")
        assert len(result.text.splitlines()) == 1
        assert result.text.startswith("     \u2022")
