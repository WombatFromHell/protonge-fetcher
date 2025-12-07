"""
Unit tests for utility functions in protonfetcher.py
"""

import pytest

from protonfetcher.common import ForkName, VersionTuple
from protonfetcher.utils import (
    compare_versions,
    format_bytes,
    get_proton_asset_name,
    parse_version,
)


class TestUtilityFunctions:
    """Tests for utility functions."""

    @pytest.mark.parametrize(
        "tag,fork,expected",
        [
            # GE-Proton tests
            ("GE-Proton10-20", ForkName.GE_PROTON, ("GE-Proton", 10, 0, 20)),
            ("GE-Proton1-5", ForkName.GE_PROTON, ("GE-Proton", 1, 0, 5)),
            # Proton-EM tests
            ("EM-10.0-30", ForkName.PROTON_EM, ("EM", 10, 0, 30)),
            ("EM-1.5-10", ForkName.PROTON_EM, ("EM", 1, 5, 10)),
            # Edge cases
            ("invalid-tag", ForkName.GE_PROTON, ("invalid-tag", 0, 0, 0)),
            ("", ForkName.GE_PROTON, ("", 0, 0, 0)),
        ],
    )
    def test_parse_version(self, tag: str, fork: ForkName, expected: VersionTuple):
        """Test parse_version function."""
        result = parse_version(tag, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "tag1,tag2,fork,expected",
        [
            # GE-Proton comparisons
            ("GE-Proton10-20", "GE-Proton10-19", ForkName.GE_PROTON, 1),  # newer
            ("GE-Proton10-19", "GE-Proton10-20", ForkName.GE_PROTON, -1),  # older
            ("GE-Proton10-20", "GE-Proton10-20", ForkName.GE_PROTON, 0),  # equal
            (
                "GE-Proton11-20",
                "GE-Proton10-20",
                ForkName.GE_PROTON,
                1,
            ),  # major version
            (
                "GE-Proton10-21",
                "GE-Proton10-20",
                ForkName.GE_PROTON,
                1,
            ),  # minor version
            # Proton-EM comparisons
            ("EM-10.0-30", "EM-10.0-29", ForkName.PROTON_EM, 1),  # newer
            ("EM-10.0-29", "EM-10.0-30", ForkName.PROTON_EM, -1),  # older
            ("EM-10.0-30", "EM-10.0-30", ForkName.PROTON_EM, 0),  # equal
            ("EM-11.0-30", "EM-10.0-30", ForkName.PROTON_EM, 1),  # major version
            ("EM-10.1-30", "EM-10.0-30", ForkName.PROTON_EM, 1),  # minor version
        ],
    )
    def test_compare_versions(
        self, tag1: str, tag2: str, fork: ForkName, expected: int
    ):
        """Test compare_versions function."""
        result = compare_versions(tag1, tag2, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "tag,fork,expected",
        [
            ("GE-Proton10-20", ForkName.GE_PROTON, "GE-Proton10-20.tar.gz"),
            ("EM-10.0-30", ForkName.PROTON_EM, "proton-EM-10.0-30.tar.xz"),
            ("GE-Proton1-5", ForkName.GE_PROTON, "GE-Proton1-5.tar.gz"),
            ("EM-1.5-10", ForkName.PROTON_EM, "proton-EM-1.5-10.tar.xz"),
        ],
    )
    def test_get_proton_asset_name(self, tag: str, fork: ForkName, expected: str):
        """Test get_proton_asset_name function."""
        result = get_proton_asset_name(tag, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "bytes_value,expected",
        [
            (512, "512 B"),
            (1024, "1.00 KB"),
            (1024 * 1024, "1.00 MB"),
            (1024 * 1024 * 1024, "1.00 GB"),
            (2048, "2.00 KB"),
            (2 * 1024 * 1024, "2.00 MB"),
        ],
    )
    def test_format_bytes(self, bytes_value: int, expected: str):
        """Test format_bytes function."""
        result = format_bytes(bytes_value)
        assert result == expected
