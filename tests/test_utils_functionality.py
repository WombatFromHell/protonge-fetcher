"""
Tests for utility functions and managers in protonfetcher.py
"""

import pytest

from protonfetcher.cli import convert_fork_to_enum
from protonfetcher.common import ForkName
from protonfetcher.utils import compare_versions, parse_version


class TestUtils:
    """Tests for utility functions in protonfetcher.py."""

    def test_compare_versions_ge_proton_basic(self):
        """Test compare_versions with basic GE-Proton versions."""
        # Test basic comparison
        assert (
            compare_versions("GE-Proton10-20", "GE-Proton9-20", ForkName.GE_PROTON) == 1
        )  # 10-20 > 9-20
        assert (
            compare_versions("GE-Proton9-20", "GE-Proton10-20", ForkName.GE_PROTON)
            == -1
        )  # 9-20 < 10-20
        assert (
            compare_versions("GE-Proton10-20", "GE-Proton10-20", ForkName.GE_PROTON)
            == 0
        )  # 10-20 = 10-20

    def test_compare_versions_ge_proton_minor_difference(self):
        """Test compare_versions with GE-Proton versions that differ in minor version."""
        # Test minor version differences
        assert (
            compare_versions("GE-Proton10-21", "GE-Proton10-20", ForkName.GE_PROTON)
            == 1
        )  # 10-21 > 10-20
        assert (
            compare_versions("GE-Proton10-19", "GE-Proton10-20", ForkName.GE_PROTON)
            == -1
        )  # 10-19 < 10-20

    def test_compare_versions_proton_em_basic(self):
        """Test compare_versions with basic Proton-EM versions."""
        # Test basic Proton-EM comparison
        assert (
            compare_versions("EM-10.0-30", "EM-9.0-30", ForkName.PROTON_EM) == 1
        )  # 10.0-30 > 9.0-30
        assert (
            compare_versions("EM-9.0-30", "EM-10.0-30", ForkName.PROTON_EM) == -1
        )  # 9.0-30 < 10.0-30
        assert (
            compare_versions("EM-10.0-30", "EM-10.0-30", ForkName.PROTON_EM) == 0
        )  # 10.0-30 = 10.0-30

    def test_compare_versions_proton_em_minor_patch(self):
        """Test compare_versions with Proton-EM versions that differ in minor or patch."""
        # Test minor differences
        assert (
            compare_versions("EM-10.1-30", "EM-10.0-30", ForkName.PROTON_EM) == 1
        )  # 10.1-30 > 10.0-30
        assert (
            compare_versions("EM-10.0-29", "EM-10.0-30", ForkName.PROTON_EM) == -1
        )  # 10.0-29 < 10.0-30

    def test_compare_versions_different_forks(self):
        """Test that comparing between forks works correctly."""
        # These should still work since they're parsed according to the fork
        assert (
            compare_versions("GE-Proton10-20", "GE-Proton9-20", ForkName.GE_PROTON) == 1
        )
        assert compare_versions("EM-10.0-30", "EM-9.0-30", ForkName.PROTON_EM) == 1

    def test_parse_version_ge_proton(self):
        """Test parse_version with GE-Proton format."""
        result = parse_version("GE-Proton10-20", ForkName.GE_PROTON)
        assert result == ("GE-Proton", 10, 0, 20)

        result = parse_version("GE-Proton9-15", ForkName.GE_PROTON)
        assert result == ("GE-Proton", 9, 0, 15)

    def test_parse_version_ge_proton_invalid(self):
        """Test parse_version with invalid GE-Proton format."""
        result = parse_version("invalid-format", ForkName.GE_PROTON)
        # Should return fallback tuple
        assert result == ("invalid-format", 0, 0, 0)

    def test_parse_version_proton_em(self):
        """Test parse_version with Proton-EM format."""
        result = parse_version("EM-10.0-30", ForkName.PROTON_EM)
        assert result == ("EM", 10, 0, 30)

        result = parse_version("EM-9.5-25", ForkName.PROTON_EM)
        assert result == ("EM", 9, 5, 25)

    def test_parse_version_proton_em_invalid(self):
        """Test parse_version with invalid Proton-EM format."""
        result = parse_version("invalid-format", ForkName.PROTON_EM)
        # Should return fallback tuple
        assert result == ("invalid-format", 0, 0, 0)

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
