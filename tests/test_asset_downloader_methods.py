"""
Tests for AssetDownloader methods in protonfetcher.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add the project directory to the Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from protonfetcher.asset_downloader import AssetDownloader  # noqa: E402


class TestAssetDownloader:
    """Tests for AssetDownloader methods."""

    def test_download_asset_success(self, tmp_path, mocker):
        """Test download_asset method for successful download."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        downloader = AssetDownloader(
            network_client=mock_network, file_system_client=mock_fs
        )

        # Mock the release_manager for asset size check
        mock_release_manager = MagicMock()
        mock_release_manager.get_remote_asset_size.return_value = 1024 * 1024  # 1MB

        # Mock download to succeed
        mock_network.download.return_value = MagicMock(returncode=0, stderr="")

        # Mock file system operations
        asset_path = tmp_path / "test-asset.tar.gz"
        mock_stat = mocker.patch.object(Path, "stat")
        mock_stat.return_value = MagicMock(st_size=1024 * 1024)  # 1MB
        mock_fs.exists.return_value = False  # File doesn't exist initially

        # Mock the spinner progress display
        mock_spinner_cls = mocker.patch("protonfetcher.spinner.Spinner")
        mock_spinner_instance = MagicMock()
        mock_spinner_cls.return_value = mock_spinner_instance

        result = downloader.download_asset(
            "test/repo",
            "test-tag",
            "test-asset.tar.gz",
            asset_path,
            mock_release_manager,
        )

        # Should return the path to the downloaded asset
        assert result == asset_path
        mock_network.download.assert_called_once()

    def test_download_asset_file_exists_with_correct_size(self, tmp_path, mocker):
        """Test download_asset when file already exists with correct size."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        downloader = AssetDownloader(
            network_client=mock_network, file_system_client=mock_fs
        )

        # Mock the release_manager for asset size check
        mock_release_manager = MagicMock()
        remote_size = 1024 * 1024  # 1MB
        mock_release_manager.get_remote_asset_size.return_value = remote_size

        # Create and mock the asset path
        asset_path = tmp_path / "test-asset.tar.gz"
        mock_fs.exists.return_value = True

        # CRITICAL: Mock Path.stat() since the code calls out_path.stat().st_size directly
        mock_stat = mocker.patch.object(Path, "stat")
        mock_stat.return_value = MagicMock(st_size=remote_size)

        # Execute
        result = downloader.download_asset(
            "test/repo",
            "test-tag",
            "test-asset.tar.gz",
            asset_path,  # ✅ Pass file path, not directory
            mock_release_manager,
        )

        # Assert
        assert result == asset_path
        # Verify network download was NOT called (since file exists with correct size)
        mock_network.download.assert_not_called()
