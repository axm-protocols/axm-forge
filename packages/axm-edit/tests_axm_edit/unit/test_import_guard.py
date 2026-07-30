"""Unit tests for the orphan-import detector (memory-only, no I/O)."""

from __future__ import annotations

from axm_edit.import_guard import (
    ImportGuardReport,
    OrphanImportViolation,
    detect_orphan_imports,
)


def test_import_and_consumer_in_same_batch_yields_clean_report() -> None:
    """An import whose consumer lands in the same op set is not an orphan."""
    operation_set = {
        "path": "/proj",
        "operations": [
            {
                "op": "create",
                "file": "consumer.py",
                "content": "from mod import Widget\n\nw = Widget()\n",
            },
        ],
    }

    report = detect_orphan_imports(operation_set)

    assert report.verdict is True
    assert report.violations == []


def test_cross_file_consumer_in_same_batch_yields_clean_report() -> None:
    """The consumer may live in a different file of the same batch."""
    operation_set = {
        "path": "/proj",
        "operations": [
            {
                "op": "create",
                "file": "provider.py",
                "content": "from mod import Widget\n",
            },
            {
                "op": "create",
                "file": "user.py",
                "content": "result = Widget()\n",
            },
        ],
    }

    report = detect_orphan_imports(operation_set)

    assert report.verdict is True


def test_import_added_without_any_in_batch_consumer_flags_a_violation() -> None:
    """An import with no consumer anywhere in the batch is an orphan."""
    operation_set = {
        "path": "/proj",
        "operations": [
            {
                "op": "create",
                "file": "orphan.py",
                "content": "import os\n",
            },
        ],
    }

    report = detect_orphan_imports(operation_set)

    assert report.verdict is False
    assert len(report.violations) == 1
    violation = report.violations[0]
    assert violation.file == "orphan.py"
    assert violation.imported_name == "os"


def test_import_consumed_only_by_pre_existing_untouched_code_is_not_flagged() -> None:
    """A pre-existing consumer (``old`` text) suppresses the violation.

    The batch adds ``import json`` to a module that already uses ``json`` — the
    fix for a genuinely missing import. The consumer pre-exists (it is in the
    ``old``, untouched-by-the-batch code), so this is not an orphan. A retained
    but unused pre-existing import (``os``) must likewise never be flagged.
    """
    operation_set = {
        "path": "/proj",
        "operations": [
            {
                "op": "replace",
                "file": "mod.py",
                "edits": [
                    {
                        "old": "import os\n\nvalue = json.dumps(payload)\n",
                        "new": (
                            "import os\nimport json\n\nvalue = json.dumps(payload)\n"
                        ),
                    }
                ],
            },
        ],
    }

    report = detect_orphan_imports(operation_set)

    assert report.verdict is True
    assert report.violations == []


def test_report_exposes_structured_violation_fields() -> None:
    """The report surfaces file, imported_name and reason on each violation."""
    violation = OrphanImportViolation(
        file="a.py", imported_name="os", reason="no consumer in batch"
    )
    report = ImportGuardReport(violations=[violation])

    assert report.violations[0].file == "a.py"
    assert report.violations[0].imported_name == "os"
    assert report.violations[0].reason == "no consumer in batch"
    assert report.verdict is False
