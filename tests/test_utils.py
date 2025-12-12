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


class TestUtilityFunctionsBranchCoverage:
    """Branch-specific tests for utility functions to extend code coverage."""

    def test_validate_protocol_instance_missing_method(self, mocker):
        """Test validate_protocol_instance when object is missing required method."""
        from protonfetcher.common import NetworkClientProtocol
        from protonfetcher.utils import validate_protocol_instance

        # Create a mock object that doesn't implement the protocol
        class FakeClient:
            def __init__(self):
                pass
                # Missing required methods from NetworkClientProtocol

        fake_client = FakeClient()
        result = validate_protocol_instance(fake_client, NetworkClientProtocol)
        assert result is False

    def test_validate_protocol_instance_non_callable_attribute(self, mocker):
        """Test validate_protocol_instance when object has non-callable attribute."""
        from protonfetcher.common import NetworkClientProtocol
        from protonfetcher.utils import validate_protocol_instance

        # Create a mock object with non-callable attributes
        class FakeClient:
            def __init__(self):
                self.fetch = "not callable"  # Should be a method

        fake_client = FakeClient()
        result = validate_protocol_instance(fake_client, NetworkClientProtocol)
        assert result is False

    def test_validate_protocol_instance_exception_during_validation(self, mocker):
        """Test validate_protocol_instance when validation raises exception."""
        from protonfetcher.common import NetworkClientProtocol
        from protonfetcher.utils import validate_protocol_instance

        # Create a mock object that raises exception during validation
        class ProblematicClient:
            def __init__(self):
                pass

            def __getattr__(self, name):
                if name == "fetch":
                    raise Exception("Attribute access error")
                return super().__getattribute__(name)

        problematic_client = ProblematicClient()
        result = validate_protocol_instance(problematic_client, NetworkClientProtocol)
        assert result is False

    def test_validate_protocol_instance_empty_protocol(self, mocker):
        """Test validate_protocol_instance with empty protocol."""
        from typing import Protocol

        from protonfetcher.utils import validate_protocol_instance

        # Create an empty protocol
        class EmptyProtocol(Protocol):
            pass

        class TestObject:
            pass

        test_obj = TestObject()
        result = validate_protocol_instance(test_obj, EmptyProtocol)
        assert result is True

    @pytest.mark.parametrize(
        "tag,fork",
        [
            ("invalid-ge-format", ForkName.GE_PROTON),
            ("GE-Proton", ForkName.GE_PROTON),  # Missing version numbers
            ("GE-Proton-", ForkName.GE_PROTON),  # Incomplete version
            ("GE-Proton-abc", ForkName.GE_PROTON),  # Non-numeric version
            ("invalid-em-format", ForkName.PROTON_EM),
            ("EM-", ForkName.PROTON_EM),  # Incomplete version
            ("EM-abc.def-ghi", ForkName.PROTON_EM),  # Non-numeric version
        ],
    )
    def test_parse_version_invalid_formats(self, tag: str, fork: ForkName):
        """Test parse_version with various invalid format edge cases."""
        result = parse_version(tag, fork)
        # All invalid formats should return fallback tuple with original tag
        assert result[0] == tag
        assert result[1:] == (0, 0, 0)

    def test_parse_version_unexpected_fork_value(self):
        """Test parse_version with unexpected fork value."""
        # Test with a fork that doesn't match expected patterns
        # This should still work and return fallback values
        result = parse_version("test-tag", ForkName.GE_PROTON)
        # Should return parsed values, not necessarily fallback
        assert result == ("test-tag", 0, 0, 0)

    @pytest.mark.parametrize(
        "tag1,tag2,fork,expected",
        [
            # Test all comparison branches for GE-Proton
            ("GE-Proton10-20", "GE-Proton10-20", ForkName.GE_PROTON, 0),  # Equal
            (
                "GE-Proton10-20",
                "GE-Proton10-19",
                ForkName.GE_PROTON,
                1,
            ),  # Greater (patch)
            (
                "GE-Proton10-19",
                "GE-Proton10-20",
                ForkName.GE_PROTON,
                -1,
            ),  # Less (patch)
            (
                "GE-Proton11-20",
                "GE-Proton10-20",
                ForkName.GE_PROTON,
                1,
            ),  # Greater (major)
            (
                "GE-Proton10-20",
                "GE-Proton11-20",
                ForkName.GE_PROTON,
                -1,
            ),  # Less (major)
            # Test all comparison branches for Proton-EM
            ("EM-10.0-30", "EM-10.0-30", ForkName.PROTON_EM, 0),  # Equal
            ("EM-10.0-30", "EM-10.0-29", ForkName.PROTON_EM, 1),  # Greater (patch)
            ("EM-10.0-29", "EM-10.0-30", ForkName.PROTON_EM, -1),  # Less (patch)
            ("EM-11.0-30", "EM-10.0-30", ForkName.PROTON_EM, 1),  # Greater (major)
            ("EM-10.0-30", "EM-11.0-30", ForkName.PROTON_EM, -1),  # Less (major)
            ("EM-10.1-30", "EM-10.0-30", ForkName.PROTON_EM, 1),  # Greater (minor)
            ("EM-10.0-30", "EM-10.1-30", ForkName.PROTON_EM, -1),  # Less (minor)
            # Test prefix comparison
            (
                "EM-10.0-30",
                "GE-Proton10-20",
                ForkName.GE_PROTON,
                -1,
            ),  # Different prefixes
            (
                "GE-Proton10-20",
                "EM-10.0-30",
                ForkName.GE_PROTON,
                1,
            ),  # Different prefixes
        ],
    )
    def test_compare_versions_all_branches(
        self, tag1: str, tag2: str, fork: ForkName, expected: int
    ):
        """Test compare_versions covering all comparison branches."""
        result = compare_versions(tag1, tag2, fork)
        assert result == expected

    @pytest.mark.parametrize(
        "tag,fork",
        [
            ("", ForkName.GE_PROTON),
            (" ", ForkName.GE_PROTON),
            ("special-chars-!@#", ForkName.GE_PROTON),
            ("unicode-测试", ForkName.GE_PROTON),
            ("", ForkName.PROTON_EM),
            ("very-long-tag-name-that-exceeds-normal-lengths", ForkName.PROTON_EM),
        ],
    )
    def test_get_proton_asset_name_edge_cases(self, tag: str, fork: ForkName):
        """Test get_proton_asset_name with edge case tag formats."""
        result = get_proton_asset_name(tag, fork)

        if fork == ForkName.PROTON_EM:
            assert result == f"proton-{tag}.tar.xz"
        else:
            assert result == f"{tag}.tar.gz"

    @pytest.mark.parametrize(
        "bytes_value",
        [
            0,  # Zero bytes
            1,  # 1 byte
            1023,  # Just under 1KB
            1024,  # Exactly 1KB
            1025,  # Just over 1KB
            1024 * 1024 - 1,  # Just under 1MB
            1024 * 1024,  # Exactly 1MB
            1024 * 1024 + 1,  # Just over 1MB
            1024 * 1024 * 1024 - 1,  # Just under 1GB
            1024 * 1024 * 1024,  # Exactly 1GB
            1024 * 1024 * 1024 + 1,  # Just over 1GB
            1024 * 1024 * 1024 * 2,  # 2GB
        ],
    )
    def test_format_bytes_boundary_values(self, bytes_value: int):
        """Test format_bytes with boundary values to cover all formatting branches."""
        result = format_bytes(bytes_value)

        # Verify the result contains appropriate units
        if bytes_value < 1024:
            assert result.endswith(" B")
        elif bytes_value < 1024 * 1024:
            assert result.endswith(" KB")
        elif bytes_value < 1024 * 1024 * 1024:
            assert result.endswith(" MB")
        else:
            assert result.endswith(" GB")

    def test_format_bytes_negative_value(self):
        """Test format_bytes with negative value (edge case)."""
        # This tests the else branch when value doesn't match any condition
        result = format_bytes(-100)
        # Negative values are treated as bytes (first condition: -100 < 1024)
        assert result.endswith(" B")


class TestUtilityFunctionsBranchCoverageAdditional:
    """Additional branch-specific tests for utility functions to extend code coverage."""

    def test_validate_protocol_instance_valid_protocol(self, mocker):
        """Test validate_protocol_instance with valid protocol implementation."""
        from protonfetcher.common import NetworkClientProtocol
        from protonfetcher.utils import validate_protocol_instance

        # Create a valid mock implementation with all required methods and attributes
        class ValidClient:
            def __init__(self):
                self.timeout = 60
                self.PROTOCOL_VERSION = "1.0"

            def get(self, url, headers=None, stream=False):
                return type(
                    "obj", (object,), {"stdout": "mock", "stderr": "", "returncode": 0}
                )()

            def head(self, url, headers=None, follow_redirects=False):
                return type(
                    "obj", (object,), {"stdout": "mock", "stderr": "", "returncode": 0}
                )()

            def download(self, url, output_path, headers=None):
                return type(
                    "obj", (object,), {"stdout": "mock", "stderr": "", "returncode": 0}
                )()

        valid_client = ValidClient()
        result = validate_protocol_instance(valid_client, NetworkClientProtocol)
        assert result is True

    def test_validate_protocol_instance_missing_method(self, mocker):
        """Test validate_protocol_instance when object is missing required method."""
        from protonfetcher.common import NetworkClientProtocol
        from protonfetcher.utils import validate_protocol_instance

        # Create a mock object that doesn't implement the protocol
        class FakeClient:
            def __init__(self):
                pass
                # Missing required methods from NetworkClientProtocol

        fake_client = FakeClient()
        result = validate_protocol_instance(fake_client, NetworkClientProtocol)
        assert result is False

    def test_validate_protocol_instance_non_callable_attribute(self, mocker):
        """Test validate_protocol_instance when object has non-callable attribute."""
        from protonfetcher.common import NetworkClientProtocol
        from protonfetcher.utils import validate_protocol_instance

        # Create a mock object with non-callable attributes
        class FakeClient:
            def __init__(self):
                self.fetch = "not callable"  # Should be a method

        fake_client = FakeClient()
        result = validate_protocol_instance(fake_client, NetworkClientProtocol)
        assert result is False

    def test_validate_protocol_instance_exception_during_validation(self, mocker):
        """Test validate_protocol_instance when validation raises exception."""
        from protonfetcher.common import NetworkClientProtocol
        from protonfetcher.utils import validate_protocol_instance

        # Create a mock object that raises exception during validation
        class ProblematicClient:
            def __init__(self):
                pass

            def __getattr__(self, name):
                if name == "fetch":
                    raise Exception("Attribute access error")
                return super().__getattribute__(name)

        problematic_client = ProblematicClient()
        result = validate_protocol_instance(problematic_client, NetworkClientProtocol)
        assert result is False

    def test_validate_protocol_instance_empty_protocol(self, mocker):
        """Test validate_protocol_instance with empty protocol."""
        from typing import Protocol

        from protonfetcher.utils import validate_protocol_instance

        # Create an empty protocol
        class EmptyProtocol(Protocol):
            pass

        class TestObject:
            pass

        test_obj = TestObject()
        result = validate_protocol_instance(test_obj, EmptyProtocol)
        assert result is True

    def test_parse_version_ge_proton_valid_formats(self):
        """Test parse_version with valid GE-Proton formats."""
        # Test valid GE-Proton formats
        result1 = parse_version("GE-Proton10-20", ForkName.GE_PROTON)
        assert result1 == ("GE-Proton", 10, 0, 20)

        result2 = parse_version("GE-Proton9-15", ForkName.GE_PROTON)
        assert result2 == ("GE-Proton", 9, 0, 15)

        result3 = parse_version("GE-Proton1-5", ForkName.GE_PROTON)
        assert result3 == ("GE-Proton", 1, 0, 5)

    def test_parse_version_proton_em_valid_formats(self):
        """Test parse_version with valid Proton-EM formats."""
        # Test valid Proton-EM formats
        result1 = parse_version("EM-10.0-30", ForkName.PROTON_EM)
        assert result1 == ("EM", 10, 0, 30)

        result2 = parse_version("EM-10.5-25", ForkName.PROTON_EM)
        assert result2 == ("EM", 10, 5, 25)

        result3 = parse_version("EM-1.5-10", ForkName.PROTON_EM)
        assert result3 == ("EM", 1, 5, 10)

    def test_parse_version_invalid_formats(self):
        """Test parse_version with various invalid format edge cases."""
        # Test invalid formats for both forks
        result1 = parse_version("invalid-ge-format", ForkName.GE_PROTON)
        assert result1 == ("invalid-ge-format", 0, 0, 0)

        result2 = parse_version("GE-Proton", ForkName.GE_PROTON)
        assert result2 == ("GE-Proton", 0, 0, 0)

        result3 = parse_version("GE-Proton-", ForkName.GE_PROTON)
        assert result3 == ("GE-Proton-", 0, 0, 0)

        result4 = parse_version("GE-Proton-abc", ForkName.GE_PROTON)
        assert result4 == ("GE-Proton-abc", 0, 0, 0)

        result5 = parse_version("invalid-em-format", ForkName.PROTON_EM)
        assert result5 == ("invalid-em-format", 0, 0, 0)

        result6 = parse_version("EM-", ForkName.PROTON_EM)
        assert result6 == ("EM-", 0, 0, 0)

        result7 = parse_version("EM-abc.def-ghi", ForkName.PROTON_EM)
        assert result7 == ("EM-abc.def-ghi", 0, 0, 0)

    def test_compare_versions_all_comparison_branches(self):
        """Test compare_versions covering all comparison branches."""
        # Test all comparison branches for GE-Proton
        assert (
            compare_versions("GE-Proton10-20", "GE-Proton10-20", ForkName.GE_PROTON)
            == 0
        )  # Equal
        assert (
            compare_versions("GE-Proton10-20", "GE-Proton10-19", ForkName.GE_PROTON)
            == 1
        )  # Greater (patch)
        assert (
            compare_versions("GE-Proton10-19", "GE-Proton10-20", ForkName.GE_PROTON)
            == -1
        )  # Less (patch)
        assert (
            compare_versions("GE-Proton11-20", "GE-Proton10-20", ForkName.GE_PROTON)
            == 1
        )  # Greater (major)
        assert (
            compare_versions("GE-Proton10-20", "GE-Proton11-20", ForkName.GE_PROTON)
            == -1
        )  # Less (major)

        # Test all comparison branches for Proton-EM
        assert (
            compare_versions("EM-10.0-30", "EM-10.0-30", ForkName.PROTON_EM) == 0
        )  # Equal
        assert (
            compare_versions("EM-10.0-30", "EM-10.0-29", ForkName.PROTON_EM) == 1
        )  # Greater (patch)
        assert (
            compare_versions("EM-10.0-29", "EM-10.0-30", ForkName.PROTON_EM) == -1
        )  # Less (patch)
        assert (
            compare_versions("EM-11.0-30", "EM-10.0-30", ForkName.PROTON_EM) == 1
        )  # Greater (major)
        assert (
            compare_versions("EM-10.0-30", "EM-11.0-30", ForkName.PROTON_EM) == -1
        )  # Less (major)
        assert (
            compare_versions("EM-10.1-30", "EM-10.0-30", ForkName.PROTON_EM) == 1
        )  # Greater (minor)
        assert (
            compare_versions("EM-10.0-30", "EM-10.1-30", ForkName.PROTON_EM) == -1
        )  # Less (minor)

        # Test prefix comparison
        assert (
            compare_versions("EM-10.0-30", "GE-Proton10-20", ForkName.GE_PROTON) == -1
        )  # Different prefixes
        assert (
            compare_versions("GE-Proton10-20", "EM-10.0-30", ForkName.GE_PROTON) == 1
        )  # Different prefixes

    def test_get_proton_asset_name_edge_cases(self):
        """Test get_proton_asset_name with edge case tag formats."""
        # Test edge cases for both forks
        result1 = get_proton_asset_name("", ForkName.GE_PROTON)
        assert result1 == ".tar.gz"

        result2 = get_proton_asset_name(" ", ForkName.GE_PROTON)
        assert result2 == " .tar.gz"

        result3 = get_proton_asset_name("special-chars-!@#", ForkName.GE_PROTON)
        assert result3 == "special-chars-!@#.tar.gz"

        result4 = get_proton_asset_name("unicode-测试", ForkName.GE_PROTON)
        assert result4 == "unicode-测试.tar.gz"

        result5 = get_proton_asset_name("", ForkName.PROTON_EM)
        assert result5 == "proton-.tar.xz"

        result6 = get_proton_asset_name(
            "very-long-tag-name-that-exceeds-normal-lengths", ForkName.PROTON_EM
        )
        assert result6 == "proton-very-long-tag-name-that-exceeds-normal-lengths.tar.xz"

    def test_format_bytes_boundary_values(self):
        """Test format_bytes with boundary values to cover all formatting branches."""
        # Test boundary values for all units
        result1 = format_bytes(0)  # Zero bytes
        assert result1.endswith(" B")

        result2 = format_bytes(1)  # 1 byte
        assert result2.endswith(" B")

        result3 = format_bytes(1023)  # Just under 1KB
        assert result3.endswith(" B")

        result4 = format_bytes(1024)  # Exactly 1KB
        assert result4.endswith(" KB")

        result5 = format_bytes(1025)  # Just over 1KB
        assert result5.endswith(" KB")

        result6 = format_bytes(1024 * 1024 - 1)  # Just under 1MB
        assert result6.endswith(" KB")

        result7 = format_bytes(1024 * 1024)  # Exactly 1MB
        assert result7.endswith(" MB")

        result8 = format_bytes(1024 * 1024 + 1)  # Just over 1MB
        assert result8.endswith(" MB")

        result9 = format_bytes(1024 * 1024 * 1024 - 1)  # Just under 1GB
        assert result9.endswith(" MB")

        result10 = format_bytes(1024 * 1024 * 1024)  # Exactly 1GB
        assert result10.endswith(" GB")

        result11 = format_bytes(1024 * 1024 * 1024 + 1)  # Just over 1GB
        assert result11.endswith(" GB")

        result12 = format_bytes(1024 * 1024 * 1024 * 2)  # 2GB
        assert result12.endswith(" GB")

    def test_format_bytes_negative_and_edge_cases(self):
        """Test format_bytes with negative and other edge cases."""
        # Test negative value
        result1 = format_bytes(-100)
        assert result1.endswith(" B")
        assert result1.startswith("-")

        # Test very large value
        result2 = format_bytes(1024 * 1024 * 1024 * 1024)  # 1TB
        assert result2.endswith(" GB")  # Should still use GB for very large values
        # Large positive values don't start with "-"
        assert not result2.startswith("-")


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
