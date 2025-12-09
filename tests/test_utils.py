"""
Unit tests for utility functions in protonfetcher.py
"""

import pytest

from protonfetcher.cli import convert_fork_to_enum
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
            ("GE-Proton9-15", ForkName.GE_PROTON, ("GE-Proton", 9, 0, 15)),
            # Proton-EM tests
            ("EM-10.0-30", ForkName.PROTON_EM, ("EM", 10, 0, 30)),
            ("EM-1.5-10", ForkName.PROTON_EM, ("EM", 1, 5, 10)),
            ("EM-9.5-25", ForkName.PROTON_EM, ("EM", 9, 5, 25)),
            # Edge cases and invalid formats
            ("invalid-tag", ForkName.GE_PROTON, ("invalid-tag", 0, 0, 0)),
            ("invalid-format", ForkName.GE_PROTON, ("invalid-format", 0, 0, 0)),
            ("invalid-format", ForkName.PROTON_EM, ("invalid-format", 0, 0, 0)),
            ("", ForkName.GE_PROTON, ("", 0, 0, 0)),
        ],
    )
    def test_parse_version(self, tag: str, fork: ForkName, expected: VersionTuple):
        """Test parse_version function with various inputs."""
        result = parse_version(tag, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "tag1,tag2,fork,expected",
        [
            # GE-Proton comparisons - equality and ordering
            ("GE-Proton10-20", "GE-Proton10-19", ForkName.GE_PROTON, 1),  # newer
            ("GE-Proton10-19", "GE-Proton10-20", ForkName.GE_PROTON, -1),  # older
            ("GE-Proton10-20", "GE-Proton10-20", ForkName.GE_PROTON, 0),  # equal
            # GE-Proton basic comparisons
            ("GE-Proton10-20", "GE-Proton9-20", ForkName.GE_PROTON, 1),  # 10-20 > 9-20
            ("GE-Proton9-20", "GE-Proton10-20", ForkName.GE_PROTON, -1),  # 9-20 < 10-20
            (
                "GE-Proton10-20",
                "GE-Proton10-20",
                ForkName.GE_PROTON,
                0,
            ),  # 10-20 = 10-20
            # GE-Proton major/minor differences
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
            (
                "GE-Proton10-21",
                "GE-Proton10-20",
                ForkName.GE_PROTON,
                1,
            ),  # 10-21 > 10-20 - minor diff
            (
                "GE-Proton10-19",
                "GE-Proton10-20",
                ForkName.GE_PROTON,
                -1,
            ),  # 10-19 < 10-20 - minor diff
            # Proton-EM comparisons - equality and ordering
            ("EM-10.0-30", "EM-10.0-29", ForkName.PROTON_EM, 1),  # newer
            ("EM-10.0-29", "EM-10.0-30", ForkName.PROTON_EM, -1),  # older
            ("EM-10.0-30", "EM-10.0-30", ForkName.PROTON_EM, 0),  # equal
            # Proton-EM basic comparisons
            ("EM-10.0-30", "EM-9.0-30", ForkName.PROTON_EM, 1),  # 10.0-30 > 9.0-30
            ("EM-9.0-30", "EM-10.0-30", ForkName.PROTON_EM, -1),  # 9.0-30 < 10.0-30
            ("EM-10.0-30", "EM-10.0-30", ForkName.PROTON_EM, 0),  # 10.0-30 = 10.0-30
            # Proton-EM major/minor differences
            ("EM-11.0-30", "EM-10.0-30", ForkName.PROTON_EM, 1),  # major version
            ("EM-10.1-30", "EM-10.0-30", ForkName.PROTON_EM, 1),  # minor version
            (
                "EM-10.1-30",
                "EM-10.0-30",
                ForkName.PROTON_EM,
                1,
            ),  # 10.1-30 > 10.0-30 - minor patch
            (
                "EM-10.0-29",
                "EM-10.0-30",
                ForkName.PROTON_EM,
                -1,
            ),  # 10.0-29 < 10.0-30 - minor patch
        ],
    )
    def test_compare_versions(
        self, tag1: str, tag2: str, fork: ForkName, expected: int
    ):
        """Test compare_versions function with various inputs."""
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

    def test_convert_fork_to_enum_valid_strings(self):
        """Test convert_fork_to_enum with valid string inputs."""
        # Import the function as it might be a local function

        assert convert_fork_to_enum("GE-Proton") == ForkName.GE_PROTON
        assert convert_fork_to_enum("Proton-EM") == ForkName.PROTON_EM

    def test_convert_fork_to_enum_valid_enum(self):
        """Test convert_fork_to_enum when passed an already valid enum."""

        assert convert_fork_to_enum(ForkName.GE_PROTON) == ForkName.GE_PROTON
        assert convert_fork_to_enum(ForkName.PROTON_EM) == ForkName.PROTON_EM

    def test_convert_fork_to_enum_invalid(self):
        """Test convert_fork_to_enum with invalid inputs."""

        # The function raises SystemExit(1) for invalid forks
        with pytest.raises(SystemExit) as exc_info:
            convert_fork_to_enum("Invalid-Fork")

        assert exc_info.value.code == 1

    def test_convert_fork_to_enum_none(self):
        """Test convert_fork_to_enum with None input."""

        # This should return the default fork
        result = convert_fork_to_enum(None)
        assert result == ForkName.GE_PROTON  # Default fork should be GE-Proton
