"""
Unit tests for GitHubReleaseFetcher in protonfetcher.py
"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protonfetcher import (
    ExtractionError,
    ForkName,
    GitHubReleaseFetcher,
    LinkManagementError,
    NetworkError,
    ProtonFetcherError,
)


class TestGitHubReleaseFetcher:
    """Tests for GitHubReleaseFetcher class."""

    def test_init(self, mocker):
        """Test GitHubReleaseFetcher initialization."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        assert fetcher.timeout == 60
        assert fetcher.network_client == mock_network
        assert fetcher.file_system_client == mock_fs

    def test_fetch_and_extract_success(self, mocker, tmp_path):
        """Test fetch_and_extract method with successful complete workflow."""
        import shutil

        # Mock shutil.which to return curl path for validation
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock all dependencies
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        # Mock the link manager method that will be called
        mock_link_manager.manage_proton_links.return_value = True

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup mocks for successful workflow
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / "GE-Proton10-20.tar.gz"
        )
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / "GE-Proton10-20"
        )

        # Mock the basic filesystem operations needed for directory validation to pass
        def mock_fs_exists(path):
            # Return True for download and extract directories to pass validation
            return str(path) in [str(tmp_path / "Downloads"), str(tmp_path / "extract")]

        def mock_fs_is_dir(path):
            # Return True for download and extract directories to pass validation
            return str(path) in [str(tmp_path / "Downloads"), str(tmp_path / "extract")]

        def mock_fs_mkdir(path, parents=False, exist_ok=False):
            # Mock mkdir to prevent errors
            pass

        def mock_fs_write(path, data):
            # Mock write to allow directory write test to pass
            pass

        def mock_fs_unlink(path):
            # Mock unlink to allow directory write test to pass
            pass

        fetcher.file_system_client.exists.side_effect = mock_fs_exists  # type: ignore
        fetcher.file_system_client.is_dir.side_effect = mock_fs_is_dir  # type: ignore
        fetcher.file_system_client.mkdir.side_effect = mock_fs_mkdir  # type: ignore
        fetcher.file_system_client.write.side_effect = mock_fs_write  # type: ignore
        fetcher.file_system_client.unlink.side_effect = mock_fs_unlink  # type: ignore

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        result = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,  # Fetch latest
            fork=ForkName.GE_PROTON,
        )

        assert result == tmp_path / "extract" / "GE-Proton10-20"
        # Verify all methods were called in the right order
        mock_release_manager.fetch_latest_tag.assert_called_once()
        mock_release_manager.find_asset_by_name.assert_called_once()
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_fetch_and_extract_with_manual_tag(self, mocker, tmp_path):
        """Test fetch_and_extract method with manual release tag."""
        import shutil

        # Mock shutil.which to return curl path for validation
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock all dependencies
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup mocks for successful workflow with manual tag
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / "GE-Proton10-20.tar.gz"
        )
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / "GE-Proton10-20"
        )

        # Mock the basic filesystem operations needed for directory validation to pass
        def mock_fs_exists(path):
            # Return True for download and extract directories to pass validation
            return str(path) in [str(tmp_path / "Downloads"), str(tmp_path / "extract")]

        def mock_fs_is_dir(path):
            # Return True for download and extract directories to pass validation
            return str(path) in [str(tmp_path / "Downloads"), str(tmp_path / "extract")]

        def mock_fs_mkdir(path, parents=False, exist_ok=False):
            # Mock mkdir to prevent errors
            pass

        def mock_fs_write(path, data):
            # Mock write to allow directory write test to pass
            pass

        def mock_fs_unlink(path):
            # Mock unlink to allow directory write test to pass
            pass

        fetcher.file_system_client.exists.side_effect = mock_fs_exists  # type: ignore
        fetcher.file_system_client.is_dir.side_effect = mock_fs_is_dir  # type: ignore
        fetcher.file_system_client.mkdir.side_effect = mock_fs_mkdir  # type: ignore
        fetcher.file_system_client.write.side_effect = mock_fs_write  # type: ignore
        fetcher.file_system_client.unlink.side_effect = mock_fs_unlink  # type: ignore

        mock_link_manager.manage_proton_links.return_value = True

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        result = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag="GE-Proton10-20",  # Manual tag
            fork=ForkName.GE_PROTON,
        )

        assert result == tmp_path / "extract" / "GE-Proton10-20"
        # Verify fetch_latest_tag was NOT called since we provided a manual tag
        mock_release_manager.fetch_latest_tag.assert_not_called()
        # Verify find_asset was called with the manual tag
        mock_release_manager.find_asset_by_name.assert_called_once_with(
            "GloriousEggroll/proton-ge-custom", "GE-Proton10-20", ForkName.GE_PROTON
        )
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_fetch_and_extract_network_error(self, mocker):
        """Test fetch_and_extract method with network error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock all dependencies
        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager

        # Setup mock to raise NetworkError
        mock_release_manager.fetch_latest_tag.side_effect = NetworkError(  # type: ignore
            "Connection failed"
        )

        with pytest.raises(NetworkError):
            fetcher.fetch_and_extract(
                repo="GloriousEggroll/proton-ge-custom",
                output_dir=Path("/tmp"),
                extract_dir=Path("/tmp"),
                release_tag=None,
                fork=ForkName.GE_PROTON,
            )

    def test_fetch_and_extract_extraction_error(self, mocker, tmp_path):
        """Test fetch_and_extract method with extraction error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock all dependencies
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor

        # Setup mocks - everything succeeds until extraction
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_release_manager.get_remote_asset_size.return_value = (
            1024 * 1024 * 400
        )  # 400MB
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / "GE-Proton10-20.tar.gz"
        )
        mock_archive_extractor.extract_archive.side_effect = ExtractionError(  # type: ignore
            "Extraction failed"
        )

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        with pytest.raises(ExtractionError):
            fetcher.fetch_and_extract(
                repo="GloriousEggroll/proton-ge-custom",
                output_dir=tmp_path / "Downloads",
                extract_dir=tmp_path / "extract",
                release_tag=None,
                fork=ForkName.GE_PROTON,
            )

    def test_fetch_and_extract_link_management_error(self, mocker, tmp_path):
        """Test fetch_and_extract method with link management error."""
        import shutil

        # Mock shutil.which to return curl path for validation
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock all dependencies
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup mocks - everything succeeds until link management
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / "GE-Proton10-20.tar.gz"
        )
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / "GE-Proton10-20"
        )

        # Mock the basic filesystem operations needed for directory validation to pass
        def mock_fs_exists(path):
            # Return True for download and extract directories to pass validation
            return str(path) in [str(tmp_path / "Downloads"), str(tmp_path / "extract")]

        def mock_fs_is_dir(path):
            # Return True for download and extract directories to pass validation
            return str(path) in [str(tmp_path / "Downloads"), str(tmp_path / "extract")]

        def mock_fs_mkdir(path, parents=False, exist_ok=False):
            # Mock mkdir to prevent errors
            pass

        def mock_fs_write(path, data):
            # Mock write to allow directory write test to pass
            pass

        def mock_fs_unlink(path):
            # Mock unlink to allow directory write test to pass
            pass

        fetcher.file_system_client.exists.side_effect = mock_fs_exists  # type: ignore
        fetcher.file_system_client.is_dir.side_effect = mock_fs_is_dir  # type: ignore
        fetcher.file_system_client.mkdir.side_effect = mock_fs_mkdir  # type: ignore
        fetcher.file_system_client.write.side_effect = mock_fs_write  # type: ignore
        fetcher.file_system_client.unlink.side_effect = mock_fs_unlink  # type: ignore

        mock_link_manager.manage_proton_links.side_effect = LinkManagementError(  # type: ignore
            "Failed to manage proton links"
        )

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        with pytest.raises(LinkManagementError):
            fetcher.fetch_and_extract(
                repo="GloriousEggroll/proton-ge-custom",
                output_dir=tmp_path / "Downloads",
                extract_dir=tmp_path / "extract",
                release_tag=None,
                fork=ForkName.GE_PROTON,
            )

    def test_list_links_success(self, mocker, tmp_path):
        """Test list_links method with successful link listing."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock the link_manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager

        expected_links = {
            "GE-Proton": str(tmp_path / "GE-Proton10-20"),
            "GE-Proton-Fallback": str(tmp_path / "GE-Proton9-15"),
            "GE-Proton-Fallback2": None,
        }
        mock_link_manager.list_links.return_value = expected_links

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        result = fetcher.list_links(extract_dir, ForkName.GE_PROTON)

        assert result == expected_links
        mock_link_manager.list_links.assert_called_once_with(
            extract_dir, ForkName.GE_PROTON
        )

    def test_remove_release_success(self, mocker, tmp_path):
        """Test remove_release method with successful removal."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock the link_manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager

        mock_link_manager.remove_release.return_value = True

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        result = fetcher.remove_release(
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON
        )

        assert result is True
        mock_link_manager.remove_release.assert_called_once_with(
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON
        )

    def test_remove_release_not_found(self, mocker, tmp_path):
        """Test remove_release method when release is not found."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock the link_manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager

        # Mock to raise LinkManagementError when release is not found
        mock_link_manager.remove_release.side_effect = LinkManagementError(
            "Release not found"
        )

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        with pytest.raises(LinkManagementError):
            fetcher.remove_release(extract_dir, "GE-Proton99-99", ForkName.GE_PROTON)

    def test_list_recent_releases_success(self, mocker):
        """Test list_recent_releases method with successful API call."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock the release_manager
        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager

        expected_releases = ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]
        mock_release_manager.list_recent_releases.return_value = expected_releases

        result = fetcher.list_recent_releases("GloriousEggroll/proton-ge-custom")

        assert result == expected_releases
        mock_release_manager.list_recent_releases.assert_called_once_with(
            "GloriousEggroll/proton-ge-custom"
        )

    def test_list_recent_releases_network_error(self, mocker):
        """Test list_recent_releases method with network error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock the release_manager
        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager

        # Mock to raise NetworkError
        mock_release_manager.list_recent_releases.side_effect = NetworkError(
            "API error"
        )

        with pytest.raises(NetworkError):
            fetcher.list_recent_releases("GloriousEggroll/proton-ge-custom")

    def test_ensure_directory_is_writable_success(self, mocker, tmp_path):
        """Test _ensure_directory_is_writable with writable directory."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock file system operations to simulate writable directory
        def mock_exists(path):
            return True  # Directory exists

        def mock_is_dir(path):
            return True  # It's a directory

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.side_effect = mock_is_dir

        directory = tmp_path / "test_dir"
        directory.mkdir()

        # This should not raise any exception
        fetcher._ensure_directory_is_writable(directory)

    def test_ensure_directory_is_writable_not_exists(self, mocker, tmp_path):
        """Test _ensure_directory_is_writable when directory doesn't exist."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock file system operations to simulate directory not existing
        def mock_exists(path):
            return False  # Directory doesn't exist

        mock_fs.exists.side_effect = mock_exists

        directory = tmp_path / "nonexistent_dir"

        with pytest.raises(ProtonFetcherError):
            fetcher._ensure_directory_is_writable(directory)

    def test_ensure_directory_is_writable_not_dir(self, mocker, tmp_path):
        """Test _ensure_directory_is_writable when path is not a directory."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock file system operations to simulate path not being a directory
        def mock_exists(path):
            return True  # Path exists

        def mock_is_dir(path):
            return False  # But it's not a directory

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.side_effect = mock_is_dir

        # Create a file instead of directory
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("This is a file")

        with pytest.raises(ProtonFetcherError):
            fetcher._ensure_directory_is_writable(file_path)

    def test_determine_release_tag_latest(self, mocker):
        """Test _determine_release_tag method when fetching latest."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager
        expected_tag = "GE-Proton10-20"
        mock_release_manager.fetch_latest_tag.return_value = expected_tag

        result = fetcher._determine_release_tag(
            repo="GloriousEggroll/proton-ge-custom",
            manual_release_tag=None,
            fork=ForkName.GE_PROTON,
        )

        assert result == expected_tag
        mock_release_manager.fetch_latest_tag.assert_called_once_with(
            "GloriousEggroll/proton-ge-custom"
        )

    def test_determine_release_tag_manual(self, mocker):
        """Test _determine_release_tag method with manual tag."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        manual_tag = "GE-Proton10-20"
        result = fetcher._determine_release_tag(
            repo="GloriousEggroll/proton-ge-custom", release_tag=manual_tag
        )

        assert result == manual_tag
        # Should not call fetch_latest_tag since manual tag was provided
