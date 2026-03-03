"""Tests for protonfetcher.utils module."""

import pytest

from protonfetcher.common import ForkName
from protonfetcher.utils import parse_version


class TestParseVersion:
    """Tests for parse_version() function."""

    class TestGEProton:
        """Tests for GE-Proton version parsing."""

        @pytest.mark.parametrize(
            "tag,expected",
            [
                ("GE-Proton10-20", ("GE-Proton", 10, 0, 20)),
                ("GE-Proton9-15", ("GE-Proton", 9, 0, 15)),
                ("GE-Proton10-0", ("GE-Proton", 10, 0, 0)),
            ],
        )
        def test_parse_ge_proton_tag(self, tag: str, expected: tuple) -> None:
            """Test parsing GE-Proton tag format."""
            assert parse_version(tag, ForkName.GE_PROTON) == expected

        def test_parse_ge_proton_invalid_returns_fallback(self) -> None:
            """Test that invalid GE-Proton tags return fallback tuple."""
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

    class TestVersionComparison:
        """Tests for version comparison using parse_version results."""

        def test_ge_proton_version_comparison(self) -> None:
            """Test that GE-Proton versions compare correctly."""
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
