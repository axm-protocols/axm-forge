"""Unit tests for EOL preservation and non-UTF-8 guarding in batch_apply.

Covers AXM-2030 F1 (CRLF silently destroyed) and F2 (UnicodeDecodeError
escaping the BatchResult(success=False) contract).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import CreateOp, Edit, ReplaceOp

if TYPE_CHECKING:
    from pathlib import Path


def test_replace_preserves_crlf(tmp_path: Path) -> None:
    """AC1: a replace on a CRLF file keeps CRLF on the untouched lines."""
    target = tmp_path / "crlf.txt"
    target.write_bytes(b"alpha\r\nbravo\r\ncharlie\r\n")

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="crlf.txt", edits=[Edit(old="bravo", new="BRAVO")])],
    )

    assert result.success is True
    raw = target.read_bytes()
    # Untouched lines keep their CRLF; only the target content changed.
    assert raw == b"alpha\r\nBRAVO\r\ncharlie\r\n"
    assert b"\r\n" in raw


def test_replace_preserves_lf(tmp_path: Path) -> None:
    """AC2: a replace on an LF file stays LF (no regression)."""
    target = tmp_path / "lf.txt"
    target.write_bytes(b"alpha\nbravo\ncharlie\n")

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="lf.txt", edits=[Edit(old="bravo", new="BRAVO")])],
    )

    assert result.success is True
    raw = target.read_bytes()
    assert raw == b"alpha\nBRAVO\ncharlie\n"
    assert b"\r\n" not in raw


def test_replace_preserves_crlf_multiple_edits(tmp_path: Path) -> None:
    """AC1: multiple edits on a CRLF file all preserve CRLF endings."""
    target = tmp_path / "crlf_multi.txt"
    target.write_bytes(b"one\r\ntwo\r\nthree\r\nfour\r\n")

    result = batch_apply(
        tmp_path,
        [
            ReplaceOp(
                file="crlf_multi.txt",
                edits=[
                    Edit(old="one", new="ONE"),
                    Edit(old="three", new="THREE"),
                ],
            )
        ],
    )

    assert result.success is True
    assert target.read_bytes() == b"ONE\r\ntwo\r\nTHREE\r\nfour\r\n"


def test_create_preserves_crlf_content(tmp_path: Path) -> None:
    """AC1: a CreateOp whose content carries CRLF is written verbatim."""
    result = batch_apply(
        tmp_path,
        [CreateOp(file="new.txt", content="red\r\ngreen\r\nblue\r\n")],
    )

    assert result.success is True
    assert (tmp_path / "new.txt").read_bytes() == b"red\r\ngreen\r\nblue\r\n"


def test_create_preserves_lf_content(tmp_path: Path) -> None:
    """AC2: a CreateOp whose content carries LF is written verbatim (no CRLF leak)."""
    result = batch_apply(
        tmp_path,
        [CreateOp(file="new_lf.txt", content="red\ngreen\nblue\n")],
    )

    assert result.success is True
    assert (tmp_path / "new_lf.txt").read_bytes() == b"red\ngreen\nblue\n"


def test_replace_binary_is_validation_failure(tmp_path: Path) -> None:
    """AC3/AC4: a binary (null-byte) file in a ReplaceOp is a validation failure.

    No raw UnicodeDecodeError escapes batch_apply; the file is left untouched.
    """
    target = tmp_path / "binary.bin"
    original = b"alpha\x00\xff\xfe\nbravo\n"
    target.write_bytes(original)

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="binary.bin", edits=[Edit(old="bravo", new="BRAVO")])],
    )

    assert result.success is False
    assert result.error is not None
    # File untouched: validation gate rejected before any write.
    assert target.read_bytes() == original


def test_replace_non_utf8_is_validation_failure(tmp_path: Path) -> None:
    """AC3: a non-UTF-8 (invalid byte) file in a ReplaceOp is a validation failure.

    Bytes that are not binary by null/printable heuristic but still fail UTF-8
    decoding must surface as BatchResult(success=False), not an exception.
    """
    target = tmp_path / "latin1.txt"
    # 0xE9 is 'e-acute' in latin-1 but an invalid lone UTF-8 continuation byte.
    original = b"caf" + b"\xe9\n" + b"bravo\n"
    target.write_bytes(original)

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="latin1.txt", edits=[Edit(old="bravo", new="BRAVO")])],
    )

    assert result.success is False
    assert result.error is not None
    assert target.read_bytes() == original


def test_is_binary_wired_in_validation(tmp_path: Path) -> None:
    """AC4: binary detection runs in the validation gate; the file is untouched."""
    target = tmp_path / "image.bin"
    original = bytes(range(256)) * 4
    target.write_bytes(original)

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="image.bin", edits=[Edit(old="\x10\x11", new="XX")])],
    )

    assert result.success is False
    assert target.read_bytes() == original
