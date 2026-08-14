"""Tests for axm_edit.core.rewrite."""

from __future__ import annotations

import hashlib

import pytest

from axm_edit.core.rewrite import classify_rewrite_target, compute_checksum

HEX_ALPHABET = set("0123456789abcdef")
DIGEST = hashlib.sha256(b"on disk").hexdigest()
OTHER_DIGEST = hashlib.sha256(b"stale").hexdigest()


class TestComputeChecksum:
    """Tests for compute_checksum."""

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(b"", id="empty"),
            pytest.param(b"abc", id="non_empty"),
        ],
    )
    def test_is_sha256_hexdigest_of_exact_bytes(self, data: bytes) -> None:
        """AC2: the digest equals hashlib.sha256(data).hexdigest()."""
        digest = compute_checksum(data)

        assert digest == hashlib.sha256(data).hexdigest()
        assert len(digest) == 64
        assert set(digest) <= HEX_ALPHABET


class TestClassifyRewriteTarget:
    """Tests for the pure classify_rewrite_target predicate."""

    def test_valid_target_returns_none(self) -> None:
        """AC3: an existing regular file with a fresh digest is valid."""
        assert (
            classify_rewrite_target(
                exists=True,
                is_regular=True,
                actual_checksum=DIGEST,
                expected_checksum=DIGEST,
            )
            is None
        )

    def test_missing_target_outranks_stale_digest(self) -> None:
        """AC3: absence is reported before any digest mismatch."""
        assert (
            classify_rewrite_target(
                exists=False,
                is_regular=False,
                actual_checksum=None,
                expected_checksum=OTHER_DIGEST,
            )
            == "rewrite_target_missing"
        )

    def test_non_regular_target_outranks_stale_digest(self) -> None:
        """AC3: a non-regular target is reported before a digest mismatch."""
        assert (
            classify_rewrite_target(
                exists=True,
                is_regular=False,
                actual_checksum=DIGEST,
                expected_checksum=OTHER_DIGEST,
            )
            == "rewrite_target_not_regular"
        )

    def test_stale_digest_is_reported_last(self) -> None:
        """AC3: a regular existing target with a drifted digest is stale."""
        assert (
            classify_rewrite_target(
                exists=True,
                is_regular=True,
                actual_checksum=DIGEST,
                expected_checksum=OTHER_DIGEST,
            )
            == "rewrite_checksum_stale"
        )
