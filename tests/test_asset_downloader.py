"""
Optimized Unit tests for AssetDownloader in protonfetcher.py
"""

from pathlib import Path
import urllib.error
from protonfetcher.asset_downloader import AssetDownloader
from protonfetcher.exceptions import NetworkError

import pytest


# Fixtures have been centralized to conftest.py:
# - mock_dependencies fixture is now asset_downloader_dependencies
# - downloader fixture is now asset_downloader


# --- Test Class ---


class TestAssetDownloader:
    """Tests for AssetDownloader class."""

    def test_init(self, asset_downloader_dependencies):
        """Test AssetDownloader initialization."""
        downloader = AssetDownloader(
            asset_downloader_dependencies["network"],
            asset_downloader_dependencies["fs"],
            timeout=60,
        )
        assert downloader.timeout == 60
        assert downloader.network_client == asset_downloader_dependencies["network"]
        assert downloader.file_system_client == asset_downloader_dependencies["fs"]

    def test_curl_methods(
        self, asset_downloader, asset_downloader_dependencies, mocker
    ):
        """
        Combined test for simple curl wrappers (get, head) to reduce test runner overhead.
        """
        # Test GET
        mock_resp = mocker.MagicMock()
        asset_downloader_dependencies["network"].get.return_value = mock_resp

        assert asset_downloader.curl_get("https://example.com") == mock_resp
        asset_downloader_dependencies["network"].get.assert_called_with(
            "https://example.com", None, False
        )

        # Test HEAD
        asset_downloader_dependencies["network"].head.return_value = mock_resp
        assert asset_downloader.curl_head("https://example.com") == mock_resp
        asset_downloader_dependencies["network"].head.assert_called_with(
            "https://example.com", None, False
        )

    def test_curl_download_method(
        self, asset_downloader, asset_downloader_dependencies, mocker
    ):
        """Test curl_download method passes correct args."""
        mock_resp = mocker.MagicMock()
        asset_downloader_dependencies["network"].download.return_value = mock_resp

        # Use a dummy path; no real disk I/O needed
        output_path = Path("/dummy/test.tar.gz")

        result = asset_downloader.curl_download("https://example.com/file", output_path)

        asset_downloader_dependencies["network"].download.assert_called_once_with(
            "https://example.com/file", output_path, None
        )
        assert result == mock_resp

    def test_download_with_spinner_success(
        self, asset_downloader, asset_downloader_dependencies, mocker
    ):
        """Test download_with_spinner with minimal data allocation."""

        # Performance fix: Use small chunks (64 bytes) instead of 1MB
        small_chunk = b"x" * 64

        mock_response = mocker.MagicMock()
        mock_response.headers.get.return_value = "64"
        # Return data once, then empty bytes to signal EOF
        mock_response.read.side_effect = [small_chunk, b""]

        asset_downloader_dependencies[
            "urlopen"
        ].return_value.__enter__.return_value = mock_response

        # Use dummy path
        output_path = Path("/dummy/test.tar.gz")

        result = asset_downloader.download_with_spinner(
            "https://example.com/file", output_path
        )

        assert result is None
        asset_downloader_dependencies["open"].assert_called_with(output_path, "wb")

        # Verify spinner interaction (optional, but good for correctness)
        asset_downloader_dependencies["spinner_cls"].return_value.update.assert_called()

    def test_download_with_spinner_zero_size(
        self, asset_downloader, asset_downloader_dependencies, mocker
    ):
        """Test download_with_spinner handles zero size headers immediately."""
        mock_response = mocker.MagicMock()
        mock_response.headers.get.return_value = "0"
        mock_response.read.side_effect = [b""]
        asset_downloader_dependencies[
            "urlopen"
        ].return_value.__enter__.return_value = mock_response

        asset_downloader.download_with_spinner(
            "https://example.com/file", Path("/dummy/out")
        )

        asset_downloader_dependencies["open"].assert_called()

    def test_download_with_spinner_network_error(
        self, asset_downloader, asset_downloader_dependencies
    ):
        """Test that urllib errors are correctly re-raised as NetworkError."""
        asset_downloader_dependencies["urlopen"].side_effect = urllib.error.URLError(
            "Fail"
        )

        with pytest.raises(NetworkError):
            asset_downloader.download_with_spinner("https://url", Path("/dummy/out"))

    def test_download_asset_success_flow(
        self, asset_downloader, asset_downloader_dependencies, mocker
    ):
        """Test full asset download flow (check exists -> download)."""

        # Define a dynamic side effect for file existence
        # Returns False initially, but True if the download method has been called
        def exists_side_effect(path):
            if asset_downloader_dependencies["network"].download.called:
                return True
            return False

        asset_downloader_dependencies["fs"].exists.side_effect = exists_side_effect

        # Setup: Network download succeeds (fallback curl method)
        mock_download_resp = mocker.MagicMock(returncode=0, stderr="")
        asset_downloader_dependencies[
            "network"
        ].download.return_value = mock_download_resp

        # Mock the download_with_spinner method to raise an exception so it falls back to curl
        mocker.patch.object(
            asset_downloader,
            "download_with_spinner",
            side_effect=Exception("Spinner failed"),
        )

        repo = "test/repo"
        tag = "v1"
        asset = "file.tar.gz"
        path = Path("/dummy/file.tar.gz")

        result = asset_downloader.download_asset(
            repo, tag, asset, path, asset_downloader_dependencies["release_manager"]
        )

        assert result == path
        asset_downloader_dependencies["network"].download.assert_called_once()

    def test_download_asset_skips_existing(
        self, asset_downloader, asset_downloader_dependencies
    ):
        """Test download is skipped if file exists and matches size."""
        path = Path("/dummy/file.tar.gz")
        size = 1024

        # Setup: Local file matches remote size
        asset_downloader_dependencies["fs"].exists.return_value = True
        asset_downloader_dependencies["fs"].size.return_value = size
        asset_downloader_dependencies[
            "release_manager"
        ].get_remote_asset_size.return_value = size

        result = asset_downloader.download_asset(
            "repo",
            "tag",
            "asset",
            path,
            asset_downloader_dependencies["release_manager"],
        )

        assert result == path
        # Crucial: verify network was NOT called
        asset_downloader_dependencies["network"].download.assert_not_called()

    def test_download_asset_overwrites_wrong_size(
        self, asset_downloader, asset_downloader_dependencies, mocker
    ):
        """Test download proceeds if local file exists but has wrong size."""
        path = Path("/dummy/file.tar.gz")

        # Setup: Sizes mismatch
        asset_downloader_dependencies["fs"].exists.return_value = True
        asset_downloader_dependencies["fs"].size.return_value = 500
        asset_downloader_dependencies[
            "release_manager"
        ].get_remote_asset_size.return_value = 1000

        # Mock the download_with_spinner method to raise an exception so it falls back to curl
        mocker.patch.object(
            asset_downloader,
            "download_with_spinner",
            side_effect=Exception("Spinner failed"),
        )

        asset_downloader_dependencies[
            "network"
        ].download.return_value = mocker.MagicMock(returncode=0)

        asset_downloader.download_asset(
            "repo",
            "tag",
            "asset",
            path,
            asset_downloader_dependencies["release_manager"],
        )

        # Crucial: verify network WAS called
        asset_downloader_dependencies["network"].download.assert_called_once()

    def test_download_asset_spinner_fallback(
        self, asset_downloader, asset_downloader_dependencies, mocker
    ):
        """Test fallback to curl if urllib spinner fails."""
        path = Path("/dummy/file.tar.gz")

        asset_downloader_dependencies["fs"].exists.return_value = False

        # Mock spinner to fail, so it falls back to curl
        mocker.patch.object(
            asset_downloader,
            "download_with_spinner",
            side_effect=NetworkError("Spinner failed"),
        )

        # Setup: curl download succeeds
        mock_download_resp = mocker.MagicMock(returncode=0, stderr="")
        asset_downloader_dependencies[
            "network"
        ].download.return_value = mock_download_resp

        asset_downloader.download_asset(
            "repo",
            "tag",
            "asset",
            path,
            asset_downloader_dependencies["release_manager"],
        )

        # Verify fallback flow: spinner tried first, then curl succeeded
        asset_downloader_dependencies["network"].download.assert_called_once()
