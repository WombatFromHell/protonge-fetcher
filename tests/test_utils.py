"""Tests for protonfetcher.utils module."""

import errno
import pytest

from protonfetcher.common import ForkName
from protonfetcher.utils import describe_os_error, get_proton_asset_name, parse_version


class TestParseVersion:
    """Tests for parse_version() function."""

    class TestGEProton:
        """Tests for Proton-GE version parsing."""

        @pytest.mark.parametrize(
            "tag,expected",
            [
                ("GE-Proton10-20", ("GE-Proton", 10, 0, 20)),
                ("GE-Proton9-15", ("GE-Proton", 9, 0, 15)),
                ("GE-Proton10-0", ("GE-Proton", 10, 0, 0)),
            ],
        )
        def test_parse_ge_proton_tag(self, tag: str, expected: tuple) -> None:
            """Test parsing Proton-GE tag format."""
            assert parse_version(tag, ForkName.GE_PROTON) == expected

        def test_parse_ge_proton_invalid_returns_fallback(self) -> None:
            """Test that invalid Proton-GE tags return fallback tuple."""
            result = parse_version("invalid-tag", ForkName.GE_PROTON)
            assert result == ("invalid-tag", 0, 0, 0)

    class TestProtonEM:
        """Tests for Proton-EM version parsing."""

        @pytest.mark.parametrize(
            "tag,expected",
            [
                # Tag format (no prefix)
                ("EM-10.0-30", ("EM", 10, 0, 30)),
                ("EM-9.5-25", ("EM", 9, 5, 25)),
                # Directory format (with proton- prefix)
                ("proton-EM-10.0-30", ("EM", 10, 0, 30)),
                ("proton-EM-9.5-25", ("EM", 9, 5, 25)),
            ],
        )
        def test_parse_proton_em_tag(self, tag: str, expected: tuple) -> None:
            """Test parsing Proton-EM tag and directory formats."""
            assert parse_version(tag, ForkName.PROTON_EM) == expected

        def test_parse_proton_em_invalid_returns_fallback(self) -> None:
            """Test that invalid Proton-EM tags return fallback tuple."""
            result = parse_version("invalid-tag", ForkName.PROTON_EM)
            assert result == ("invalid-tag", 0, 0, 0)

    class TestCachyOS:
        """Tests for CachyOS version parsing."""

        @pytest.mark.parametrize(
            "tag,expected",
            [
                # Tag format (no prefix/suffix)
                ("cachyos-10.0-20260207-slr", ("cachyos", 10, 0, 20260207)),
                ("cachyos-10.0-20260227-slr", ("cachyos", 10, 0, 20260227)),
                # Directory format (with proton- prefix and -x86_64 suffix)
                (
                    "proton-cachyos-10.0-20260207-slr-x86_64",
                    ("cachyos", 10, 0, 20260207),
                ),
                (
                    "proton-cachyos-10.0-20260227-slr-x86_64",
                    ("cachyos", 10, 0, 20260227),
                ),
                # Directory format (with proton- prefix, no -x86_64 suffix)
                (
                    "proton-cachyos-10.0-20260207-slr",
                    ("cachyos", 10, 0, 20260207),
                ),
            ],
        )
        def test_parse_cachyos_tag(self, tag: str, expected: tuple) -> None:
            """Test parsing CachyOS tag and directory formats."""
            assert parse_version(tag, ForkName.CACHYOS) == expected

        def test_parse_cachyos_invalid_returns_fallback(self) -> None:
            """Test that invalid CachyOS tags return fallback tuple."""
            result = parse_version("invalid-tag", ForkName.CACHYOS)
            assert result == ("invalid-tag", 0, 0, 0)

    class TestWineland:
        """Tests for Proton-Wineland version parsing."""

        @pytest.mark.parametrize(
            "tag,expected",
            [
                ("wineland-11.0-20261005", ("wineland", 11, 0, 20261005)),
                ("wineland-11.0-20260917", ("wineland", 11, 0, 20260917)),
                # ponytail: the ".N" rebuild suffix is intentionally ignored
                # (same-date rebuilds compare equal)
                ("wineland-11.0-20260928.1", ("wineland", 11, 0, 20260928)),
            ],
        )
        def test_parse_wineland_tag(self, tag: str, expected: tuple) -> None:
            """Test parsing Proton-Wineland tag format."""
            assert parse_version(tag, ForkName.WINELAND) == expected

        def test_parse_wineland_invalid_returns_fallback(self) -> None:
            """Test that invalid Proton-Wineland tags return fallback tuple."""
            result = parse_version("invalid-tag", ForkName.WINELAND)
            assert result == ("invalid-tag", 0, 0, 0)

        def test_wineland_version_comparison(self) -> None:
            """Test that Proton-Wineland versions compare correctly (by date)."""
            v1 = parse_version("wineland-11.0-20260917", ForkName.WINELAND)
            v2 = parse_version("wineland-11.0-20261005", ForkName.WINELAND)
            assert v2 > v1

        def test_parse_wineland_raw_directory_name(self) -> None:
            """Installed dirs keep the proton- prefix and _v3 suffix; parsing must handle them.

            check_for_newer_release parses raw installed directory names, not tags.
            """
            assert parse_version(
                "proton-wineland-11.0-20261005-x86_64_v3", ForkName.WINELAND
            ) == ("wineland", 11, 0, 20261005)

        def test_wineland_asset_name(self) -> None:
            """Test that the Wineland asset name uses the _v3 variant."""
            assert (
                get_proton_asset_name("wineland-11.0-20261005", ForkName.WINELAND)
                == "proton-wineland-11.0-20261005-x86_64_v3.tar.xz"
            )

    class TestVersionComparison:
        """Tests for version comparison using parse_version results."""

        def test_ge_proton_version_comparison(self) -> None:
            """Test that Proton-GE versions compare correctly."""
            v1 = parse_version("GE-Proton10-20", ForkName.GE_PROTON)
            v2 = parse_version("GE-Proton10-21", ForkName.GE_PROTON)
            assert v2 > v1

        def test_proton_em_version_comparison(self) -> None:
            """Test that Proton-EM versions compare correctly."""
            v1 = parse_version("EM-10.0-30", ForkName.PROTON_EM)
            v2 = parse_version("EM-10.0-31", ForkName.PROTON_EM)
            assert v2 > v1
            # Also test with directory naming
            v3 = parse_version("proton-EM-10.0-30", ForkName.PROTON_EM)
            v4 = parse_version("proton-EM-10.0-31", ForkName.PROTON_EM)
            assert v4 > v3

        def test_cachyos_version_comparison(self) -> None:
            """Test that CachyOS versions compare correctly (by date)."""
            v1 = parse_version("cachyos-10.0-20260207-slr", ForkName.CACHYOS)
            v2 = parse_version("cachyos-10.0-20260227-slr", ForkName.CACHYOS)
            assert v2 > v1
            # Also test with directory naming
            v3 = parse_version(
                "proton-cachyos-10.0-20260207-slr-x86_64", ForkName.CACHYOS
            )
            v4 = parse_version(
                "proton-cachyos-10.0-20260227-slr-x86_64", ForkName.CACHYOS
            )
            assert v4 > v3

        def test_cachyos_mixed_naming_comparison(self) -> None:
            """Test that CachyOS versions compare correctly across naming conventions."""
            # Tag format vs directory format should compare correctly
            v1 = parse_version("cachyos-10.0-20260207-slr", ForkName.CACHYOS)
            v2 = parse_version(
                "proton-cachyos-10.0-20260227-slr-x86_64", ForkName.CACHYOS
            )
            assert v2 > v1


class TestDescribeOsError:
    """describe_os_error() turns an errno into plain English."""

    def test_known_errno(self) -> None:
        error = FileNotFoundError(errno.ENOENT, "No such file or directory", "/x/y")
        assert (
            describe_os_error("read", "/x/y", error)
            == "Failed to read /x/y: does not exist"
        )

    def test_permission_denied(self) -> None:
        error = PermissionError(errno.EACCES, "Permission denied", "/x")
        assert (
            describe_os_error("write", "/x", error)
            == "Failed to write /x: permission denied"
        )

    def test_unknown_errno_keeps_the_original_detail(self) -> None:
        error = OSError(errno.EIO, "Input/output error", "/x")
        assert (
            describe_os_error("write", "/x", error)
            == "Failed to write /x: [Errno 5] Input/output error: '/x'"
        )
