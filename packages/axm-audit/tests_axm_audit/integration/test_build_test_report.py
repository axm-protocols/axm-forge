"""Split from ``test_subprocess_runner_layouts.py``."""

from pathlib import Path


class TestBuildTestReport:
    """Tests for the extracted _build_test_report helper."""

    def test_build_test_report_helper(self, tmp_path: Path) -> None:
        """Tests that _build_test_report correctly constructs a TestReport."""
        from axm_audit.core.test_runner import build_test_report

        report_data = {
            "summary": {
                "passed": 2,
                "failed": 1,
                "error": 0,
                "skipped": 0,
                "warnings": 0,
            },
            "duration": 1.5,
            "tests": [
                {
                    "outcome": "failed",
                    "nodeid": "test_foo.py::test_bar",
                    "call": {
                        "crash": {
                            "message": "AssertionError: False is not True",
                            "path": "test_foo.py",
                            "lineno": 10,
                        },
                        "longrepr": "Traceback...\nAssertionError",
                    },
                }
            ],
        }

        per_file_cov = {"src/foo.py": 80.0}

        report = build_test_report(
            report_data=report_data,
            total_cov=85.0,
            per_file_cov=per_file_cov,
            mode="failures",
            last_coverage=None,
        )

        assert report.passed == 2
        assert report.failed == 1
        assert report.coverage == 85.0
        assert report.failures is not None
        assert len(report.failures) == 1
        assert report.failures[0].test == "test_foo.py::test_bar"
