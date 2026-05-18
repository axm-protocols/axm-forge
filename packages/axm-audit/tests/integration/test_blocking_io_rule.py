"""Split from ``test_practices.py``."""

from pathlib import Path

import pytest

from axm_audit.core.rules.practices.blocking_io import BlockingIORule


class TestBlockingIORuleIntegration:
    """Tests for BlockingIORule (real I/O)."""

    def test_pass_no_blocking(self, tmp_path: Path) -> None:
        """Module with async def using asyncio.sleep should pass."""
        from axm_audit.core.rules.practices.blocking_io import BlockingIORule

        src = tmp_path / "src"
        src.mkdir()
        (src / "ok.py").write_text("""\
import asyncio

async def f():
    await asyncio.sleep(1)
""")

        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.passed is True

    @pytest.mark.parametrize(
        ("source", "expected_issue"),
        [
            pytest.param(
                """\
import time

async def handler():
    time.sleep(1)
""",
                "time.sleep in async",
                id="sleep_in_async",
            ),
            pytest.param(
                """\
import requests

def fetch():
    requests.get("https://example.com")
""",
                "HTTP call without timeout",
                id="http_no_timeout",
            ),
        ],
    )
    def test_fail_blocking_violation(
        self, tmp_path: Path, source: str, expected_issue: str
    ) -> None:
        """Blocking-IO violations are detected with the expected issue label."""
        from axm_audit.core.rules.practices.blocking_io import BlockingIORule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(source)

        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        violations = result.details["violations"]
        assert len(violations) == 1
        assert violations[0]["issue"] == expected_issue

    def test_pass_with_timeout(self, tmp_path: Path) -> None:
        """requests.get with timeout should pass."""
        from axm_audit.core.rules.practices.blocking_io import BlockingIORule

        src = tmp_path / "src"
        src.mkdir()
        (src / "ok.py").write_text("""\
import requests

def fetch():
    requests.get("https://example.com", timeout=30)
""")

        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_httpx_async_client_no_timeout(self, tmp_path: Path) -> None:
        """httpx.AsyncClient().get() without timeout should fail."""
        from axm_audit.core.rules.practices.blocking_io import BlockingIORule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("""\
import httpx

async def fetch():
    httpx.AsyncClient().get("https://example.com")
""")

        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert len(result.details["violations"]) >= 1


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

    @pytest.mark.parametrize(
        ("source", "expected_bullet"),
        [
            pytest.param(
                "import time\n\nasync def f():\n    time.sleep(1)\n",
                "\u2022 bad.py:4: time.sleep in async",
                id="sleep_in_async",
            ),
            pytest.param(
                "import requests\n\ndef f():\n    requests.get('http://example.com')\n",
                "\u2022 bad.py:4: HTTP call without timeout",
                id="http_no_timeout",
            ),
        ],
    )
    def test_text_bullets_violation(
        self, tmp_path: Path, source: str, expected_bullet: str
    ) -> None:
        """Each violation kind produces its expected bullet line."""
        _write_file(tmp_path, "src/bad.py", source)
        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.text is not None
        assert expected_bullet in result.text

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
        assert all(line.startswith("\u2022") for line in lines)

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
        assert result.text.startswith("\u2022")
