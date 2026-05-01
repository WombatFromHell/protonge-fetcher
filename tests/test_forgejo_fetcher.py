"""Tests for ForgejoReleaseFetcher and DW-Proton-specific functionality."""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.common import ForkName
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.forgejo_fetcher import ForgejoReleaseFetcher
from protonfetcher.link_manager import LinkManager
from protonfetcher.utils import compare_versions, get_proton_asset_name, parse_version

# =============================================================================
# parse_version — DW-Proton
# =============================================================================


class TestParseVersionDWProton:
    """Tests for parse_version() with DW-Proton tags."""

    @pytest.mark.parametrize(
        "tag,expected",
        [
            ("dwproton-10.0-26", ("dwproton", 10, 0, 26)),
            ("dwproton-9.0-25", ("dwproton", 9, 0, 25)),
            ("dwproton-11.0-1", ("dwproton", 11, 0, 1)),
            ("dwproton-1.0-0", ("dwproton", 1, 0, 0)),
        ],
    )
    def test_parse_dwproton_tag(self, tag: str, expected: tuple) -> None:
        """Test parsing DW-Proton tag format."""
        assert parse_version(tag, ForkName.DW_PROTON) == expected

    def test_parse_dwproton_invalid_returns_fallback(self) -> None:
        """Test that invalid DW-Proton tags return fallback tuple."""
        result = parse_version("invalid-tag", ForkName.DW_PROTON)
        assert result == ("invalid-tag", 0, 0, 0)


# =============================================================================
# compare_versions — DW-Proton
# =============================================================================


class TestCompareVersionsDWProton:
    """Tests for compare_versions() with DW-Proton tags."""

    def test_dwproton_newer_version(self) -> None:
        """Test that newer DW-Proton version compares correctly."""
        assert (
            compare_versions("dwproton-10.0-27", "dwproton-10.0-26", ForkName.DW_PROTON)
            == 1
        )

    def test_dwproton_older_version(self) -> None:
        """Test that older DW-Proton version compares correctly."""
        assert (
            compare_versions("dwproton-10.0-25", "dwproton-10.0-26", ForkName.DW_PROTON)
            == -1
        )

    def test_dwproton_equal_version(self) -> None:
        """Test that equal DW-Proton versions compare as equal."""
        assert (
            compare_versions("dwproton-10.0-26", "dwproton-10.0-26", ForkName.DW_PROTON)
            == 0
        )

    def test_dwproton_major_version_comparison(self) -> None:
        """Test that major version differences are detected."""
        assert (
            compare_versions("dwproton-11.0-1", "dwproton-10.0-26", ForkName.DW_PROTON)
            == 1
        )
        assert (
            compare_versions("dwproton-9.0-25", "dwproton-10.0-26", ForkName.DW_PROTON)
            == -1
        )

    def test_dwproton_minor_version_comparison(self) -> None:
        """Test that minor version differences are detected."""
        assert (
            compare_versions("dwproton-10.1-0", "dwproton-10.0-26", ForkName.DW_PROTON)
            == 1
        )
        assert (
            compare_versions("dwproton-10.0-25", "dwproton-10.0-26", ForkName.DW_PROTON)
            == -1
        )


# =============================================================================
# get_proton_asset_name — DW-Proton
# =============================================================================


class TestGetProtonAssetNameDWProton:
    """Tests for get_proton_asset_name() with DW-Proton."""

    @pytest.mark.parametrize(
        "tag,expected",
        [
            ("dwproton-10.0-26", "dwproton-10.0-26-x86_64.tar.xz"),
            ("dwproton-9.0-25", "dwproton-9.0-25-x86_64.tar.xz"),
            ("dwproton-11.0-1", "dwproton-11.0-1-x86_64.tar.xz"),
        ],
    )
    def test_dwproton_asset_name(self, tag: str, expected: str) -> None:
        """Test asset name generation for DW-Proton."""
        assert get_proton_asset_name(tag, ForkName.DW_PROTON) == expected


# =============================================================================
# LinkManager — DW-Proton
# =============================================================================


class TestLinkManagerDWProton:
    """Tests for LinkManager with DW-Proton fork."""

    def test_get_link_names_for_fork_dwproton(self, tmp_path: Path) -> None:
        """Test get_link_names_for_fork returns correct DW-Proton symlink names."""
        fs = FileSystemClient()
        lm = LinkManager(fs)
        main, fb1, fb2 = lm.get_link_names_for_fork(tmp_path, ForkName.DW_PROTON)
        assert main == tmp_path / "DW-Proton"
        assert fb1 == tmp_path / "DW-Proton-Fallback"
        assert fb2 == tmp_path / "DW-Proton-Fallback2"

    def test_is_valid_proton_directory_dwproton(self, tmp_path: Path) -> None:
        """Test _is_valid_proton_directory with DW-Proton patterns."""
        fs = FileSystemClient()
        lm = LinkManager(fs)

        # Valid DW-Proton directories
        valid_names = [
            "dwproton-10.0-26-x86_64",
            "dwproton-9.0-25-x86_64",
            "dwproton-10.0-26-x86_64-HDRTEST",
            "dwproton-10.0-26-x86_64-RC1",
        ]
        for name in valid_names:
            dir_path = tmp_path / name
            dir_path.mkdir()
            assert lm._is_valid_proton_directory(dir_path, ForkName.DW_PROTON) is True
            dir_path.rmdir()

        # Invalid DW-Proton directories (missing -x86_64 suffix)
        invalid_names = [
            "dwproton-10.0-26",
            "GE-Proton10-20",
            "proton-EM-10.0-30",
            "proton-cachyos-10.0-20260207-slr-x86_64",
            "some-random-directory",
        ]
        for name in invalid_names:
            dir_path = tmp_path / name
            dir_path.mkdir()
            assert lm._is_valid_proton_directory(dir_path, ForkName.DW_PROTON) is False
            dir_path.rmdir()

    def test_should_skip_directory_dwproton(self, tmp_path: Path) -> None:
        """Test _should_skip_directory with DW-Proton fork."""
        fs = FileSystemClient()
        lm = LinkManager(fs)

        # DW-Proton should skip non-DW-Proton directories
        skip_names = [
            "GE-Proton10-20",
            "EM-10.0-30",
            "proton-EM-10.0-30",
            "cachyos-10.0-20260207-slr",
            "proton-cachyos-10.0-20260207-slr-x86_64",
        ]
        for name in skip_names:
            assert lm._should_skip_directory(name, ForkName.DW_PROTON) is True

        # DW-Proton should not skip its own directories
        assert (
            lm._should_skip_directory("dwproton-10.0-26-x86_64", ForkName.DW_PROTON)
            is False
        )

    def test_should_skip_directory_other_forks_skip_dwproton(
        self, tmp_path: Path
    ) -> None:
        """Test that non-DW-Proton forks skip dwproton- directories."""
        fs = FileSystemClient()
        lm = LinkManager(fs)

        for fork in [ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS]:
            assert lm._should_skip_directory("dwproton-10.0-26-x86_64", fork) is True

    def test_get_tag_name_dwproton(self, tmp_path: Path) -> None:
        """Test _get_tag_name strips -x86_64 suffix for DW-Proton."""
        fs = FileSystemClient()
        lm = LinkManager(fs)

        entry = tmp_path / "dwproton-10.0-26-x86_64"
        entry.mkdir()
        assert lm._get_tag_name(entry, ForkName.DW_PROTON) == "dwproton-10.0-26"
        entry.rmdir()

        # Without -x86_64 suffix, should return as-is
        entry2 = tmp_path / "dwproton-10.0-26"
        entry2.mkdir()
        assert lm._get_tag_name(entry2, ForkName.DW_PROTON) == "dwproton-10.0-26"
        entry2.rmdir()


# =============================================================================
# ForgejoReleaseFetcher — Unit Tests
# =============================================================================


class TestForgejoReleaseFetcher:
    """Tests for ForgejoReleaseFetcher methods."""

    def test_fetch_latest_tag_success(
        self, mocker: Any, mock_network_factory: Any
    ) -> None:
        """Test fetch_latest_tag returns tag from Forgejo API response."""
        mock_network = mock_network_factory(
            get_response={
                "tag_name": "dwproton-10.0-26",
                "name": "dwproton-10.0-26",
                "assets": [
                    {"name": "dwproton-10.0-26-x86_64.tar.xz", "size": 281758252},
                ],
            }
        )
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)
        tag = fetcher.fetch_latest_tag("dawn-winery/dwproton")
        assert tag == "dwproton-10.0-26"

    def test_fetch_latest_tag_missing_tag_name(
        self, mocker: Any, mock_network_factory: Any
    ) -> None:
        """Test fetch_latest_tag raises on missing tag_name."""
        mock_network = mock_network_factory(get_response={"name": "no tag here"})
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)
        with pytest.raises(Exception):  # NetworkError
            fetcher.fetch_latest_tag("dawn-winery/dwproton")

    def test_fetch_latest_tag_api_failure(
        self, mocker: Any, mock_network_factory: Any
    ) -> None:
        """Test fetch_latest_tag raises on API error."""
        mock_network = mock_network_factory(
            get_response="",
            custom_returncode=22,
        )
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)
        with pytest.raises(Exception):  # NetworkError
            fetcher.fetch_latest_tag("dawn-winery/dwproton")

    def test_list_recent_releases_success(
        self, mocker: Any, mock_network_factory: Any
    ) -> None:
        """Test list_recent_releases returns tag list from Forgejo API."""
        import json

        mock_network = mock_network_factory(
            get_response=json.dumps(
                [
                    {"tag_name": "dwproton-10.0-26"},
                    {"tag_name": "dwproton-10.0-25"},
                    {"tag_name": "dwproton-10.0-24"},
                ]
            )
        )
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)
        tags = fetcher.list_recent_releases("dawn-winery/dwproton")
        assert tags == ["dwproton-10.0-26", "dwproton-10.0-25", "dwproton-10.0-24"]

    def test_list_recent_releases_limits_to_20(
        self, mocker: Any, mock_network_factory: Any
    ) -> None:
        """Test list_recent_releases limits to 20 results."""
        import json

        mock_network = mock_network_factory(
            get_response=json.dumps(
                [{"tag_name": f"dwproton-10.0-{i}"} for i in range(25)]
            )
        )
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)
        tags = fetcher.list_recent_releases("dawn-winery/dwproton")
        assert len(tags) == 20

    def test_find_asset_by_name_api_success(
        self, mocker: Any, mock_network_factory: Any
    ) -> None:
        """Test find_asset_by_name finds asset via Forgejo API."""
        mock_network = mock_network_factory(
            get_response={
                "tag_name": "dwproton-10.0-26",
                "assets": [
                    {"name": "dwproton-10.0-26-x86_64.sha512sum", "size": 161},
                    {"name": "dwproton-10.0-26-x86_64.tar.xz", "size": 281758252},
                    {"name": "dwproton-10.0-26-x86_64.tar.xz.torrent", "size": 56461},
                ],
            }
        )
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)
        asset = fetcher.find_asset_by_name("dawn-winery/dwproton", "dwproton-10.0-26")
        assert asset == "dwproton-10.0-26-x86_64.tar.xz"

    def test_find_asset_by_name_api_fallback_to_first(
        self, mocker: Any, mock_network_factory: Any
    ) -> None:
        """Test find_asset_by_name falls back to first asset if no .tar.xz found."""
        mock_network = mock_network_factory(
            get_response={
                "tag_name": "dwproton-10.0-26",
                "assets": [
                    {"name": "dwproton-10.0-26-x86_64.sha512sum", "size": 161},
                ],
            }
        )
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)
        asset = fetcher.find_asset_by_name("dawn-winery/dwproton", "dwproton-10.0-26")
        assert asset == "dwproton-10.0-26-x86_64.sha512sum"

    def test_find_asset_by_name_html_fallback(
        self, mocker: Any, mock_network_factory: Any
    ) -> None:
        """Test find_asset_by_name falls back to HTML parsing when API fails."""
        # API fails
        mock_network = mock_network_factory(
            get_response="",
            custom_returncode=22,
        )
        # HTML contains the expected asset name
        html_response = '<a href="/releases/download/dwproton-10.0-26/dwproton-10.0-26-x86_64.tar.xz">dwproton-10.0-26-x86_64.tar.xz</a>'
        mock_network.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=html_response, stderr=""
        )
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)
        asset = fetcher.find_asset_by_name("dawn-winery/dwproton", "dwproton-10.0-26")
        assert asset == "dwproton-10.0-26-x86_64.tar.xz"

    def test_find_asset_by_name_returns_none_on_not_found(
        self, mocker: Any, mock_network_factory: Any
    ) -> None:
        """Test find_asset_by_name returns None when asset not found in API or HTML."""
        # API fails
        mock_network = mock_network_factory(
            get_response="",
            custom_returncode=22,
        )
        # HTML does not contain the expected asset name
        html_response = "<p>No assets found</p>"
        mock_network.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=html_response, stderr=""
        )
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)
        asset = fetcher.find_asset_by_name("dawn-winery/dwproton", "dwproton-10.0-26")
        assert asset is None

    def test_url_construction(self, mocker: Any, mock_network_factory: Any) -> None:
        """Test Forgejo URL construction helpers."""
        mock_network = mock_network_factory()
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)

        # _api_url should use dawn.wine/api/v1/repos/...
        api_url = fetcher._api_url("dawn-winery/dwproton", "releases", "latest")
        assert (
            api_url
            == "https://dawn.wine/api/v1/repos/dawn-winery/dwproton/releases/latest"
        )

        # _host_url should use dawn.wine/{owner}/{repo}/...
        host_url = fetcher._host_url(
            "dawn-winery/dwproton", "releases", "tag", "dwproton-10.0-26"
        )
        assert (
            host_url
            == "https://dawn.wine/dawn-winery/dwproton/releases/tag/dwproton-10.0-26"
        )

        download_url = fetcher._host_url(
            "dawn-winery/dwproton",
            "releases",
            "download",
            "dwproton-10.0-26",
            "dwproton-10.0-26-x86_64.tar.xz",
        )
        assert (
            download_url
            == "https://dawn.wine/dawn-winery/dwproton/releases/download/dwproton-10.0-26/dwproton-10.0-26-x86_64.tar.xz"
        )
