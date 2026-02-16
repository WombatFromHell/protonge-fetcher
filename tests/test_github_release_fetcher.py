"""
Unit tests for GitHubReleaseFetcher in protonfetcher.py
"""

from pathlib import Path

import pytest

from protonfetcher.common import ForkConfig, ForkName
from protonfetcher.exceptions import (
    ExtractionError,
    LinkManagementError,
    NetworkError,
    ProtonFetcherError,
)
from protonfetcher.github_fetcher import GitHubReleaseFetcher


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

    def test_fork_config_getitem_repo(self):
        """Test ForkConfig.__getitem__ with 'repo' key."""
        config = ForkConfig(repo="test/repo", archive_format=".tar.gz")
        assert config["repo"] == "test/repo"

    def test_fork_config_getitem_archive_format(self):
        """Test ForkConfig.__getitem__ with 'archive_format' key."""
        config = ForkConfig(repo="test/repo", archive_format=".tar.gz")
        assert config["archive_format"] == ".tar.gz"

    def test_fork_config_getitem_invalid_key_raises_keyerror(self):
        """Test ForkConfig.__getitem__ with invalid key raises KeyError."""
        config = ForkConfig(repo="test/repo", archive_format=".tar.gz")

        with pytest.raises(KeyError):
            _ = config["invalid_key"]

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_fetch_and_extract_success(self, mocker, tmp_path, fork, TEST_DATA):
        """Test fetch_and_extract method with successful complete workflow using centralized test data."""

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

        # Use centralized test data instead of inline fork-specific data
        fork_data = TEST_DATA["FORKS"][fork]
        release_tag = fork_data["example_tag"]
        asset_name = fork_data["example_asset"]
        repo = fork_data["repo"]

        mock_release_manager.fetch_latest_tag.return_value = release_tag
        mock_release_manager.find_asset_by_name.return_value = asset_name
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / asset_name
        )
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / release_tag
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
            repo=repo,
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,  # Fetch latest
            fork=fork,
        )

        assert result == tmp_path / "extract" / release_tag
        # Verify all methods were called in the right order
        mock_release_manager.fetch_latest_tag.assert_called_once()
        mock_release_manager.find_asset_by_name.assert_called_once()
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_fetch_and_extract_with_manual_tag(self, mocker, tmp_path, fork, TEST_DATA):
        """Test fetch_and_extract method with manual release tag using centralized test data."""

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

        # Use centralized test data instead of inline fork-specific data
        fork_data = TEST_DATA["FORKS"][fork]
        release_tag = fork_data["example_tag"]
        asset_name = fork_data["example_asset"]

        mock_release_manager.find_asset_by_name.return_value = asset_name
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / asset_name
        )
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / release_tag
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

        repo = (
            "GloriousEggroll/proton-ge-custom"
            if fork == ForkName.GE_PROTON
            else "acobaugh/proton-em"
        )

        result = fetcher.fetch_and_extract(
            repo=repo,
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=release_tag,  # Manual tag
            fork=fork,
        )

        assert result == tmp_path / "extract" / release_tag
        # Verify fetch_latest_tag was NOT called since we provided a manual tag
        mock_release_manager.fetch_latest_tag.assert_not_called()
        # Verify find_asset was called with the manual tag
        mock_release_manager.find_asset_by_name.assert_called_once_with(
            repo, release_tag, fork
        )
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_fetch_and_extract_network_error(self, mocker, fork, TEST_DATA):
        """Test fetch_and_extract method with network error using centralized test data."""
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
        mock_release_manager.fetch_latest_tag.side_effect = NetworkError(
            "Connection failed"
        )

        # Use centralized test data for repository
        repo = TEST_DATA["FORKS"][fork]["repo"]

        with pytest.raises(NetworkError):
            fetcher.fetch_and_extract(
                repo=repo,
                output_dir=Path("/tmp"),
                extract_dir=Path("/tmp"),
                release_tag=None,
                fork=fork,
            )

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_fetch_and_extract_extraction_error(
        self, mocker, tmp_path, fork, TEST_DATA
    ):
        """Test fetch_and_extract method with extraction error using centralized test data."""
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

        # Use centralized test data instead of inline fork-specific data
        fork_data = TEST_DATA["FORKS"][fork]
        release_tag = fork_data["example_tag"]
        asset_name = fork_data["example_asset"]
        repo = fork_data["repo"]

        mock_release_manager.fetch_latest_tag.return_value = release_tag
        mock_release_manager.find_asset_by_name.return_value = asset_name
        mock_release_manager.get_remote_asset_size.return_value = (
            1024 * 1024 * 400
        )  # 400MB
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / asset_name
        )
        mock_archive_extractor.extract_archive.side_effect = ExtractionError(
            "Extraction failed"
        )

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        with pytest.raises(ExtractionError):
            fetcher.fetch_and_extract(
                repo=repo,
                output_dir=tmp_path / "Downloads",
                extract_dir=tmp_path / "extract",
                release_tag=None,
                fork=fork,
            )

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_fetch_and_extract_link_management_error(
        self, mocker, tmp_path, fork, TEST_DATA
    ):
        """Test fetch_and_extract method with link management error using centralized test data."""

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

        # Use centralized test data instead of inline fork-specific data
        fork_data = TEST_DATA["FORKS"][fork]
        release_tag = fork_data["example_tag"]
        asset_name = fork_data["example_asset"]

        mock_release_manager.fetch_latest_tag.return_value = release_tag
        mock_release_manager.find_asset_by_name.return_value = asset_name
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / asset_name
        )
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / release_tag
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

        mock_link_manager.manage_proton_links.side_effect = LinkManagementError(
            "Failed to manage proton links"
        )

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        # Use centralized test data for repository
        repo = TEST_DATA["FORKS"][fork]["repo"]

        with pytest.raises(LinkManagementError):
            fetcher.fetch_and_extract(
                repo=repo,
                output_dir=tmp_path / "Downloads",
                extract_dir=tmp_path / "extract",
                release_tag=None,
                fork=fork,
            )

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_list_links_success(self, mocker, tmp_path, fork, TEST_DATA):
        """Test list_links method with successful link listing using centralized test data."""
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

        # Use centralized test data for link names instead of inline fork-specific data
        fork_data = TEST_DATA["FORKS"][fork]
        link_names = fork_data["link_names"]

        # Create expected links based on centralized test data
        expected_links = {
            link_names[0]: str(tmp_path / fork_data["example_tag"]),
            link_names[1]: str(
                tmp_path / "GE-Proton9-15"
                if fork == ForkName.GE_PROTON
                else "EM-9.0-20"
            ),
            link_names[2]: None,
        }

        mock_link_manager.list_links.return_value = expected_links

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        result = fetcher.list_links(extract_dir, fork)

        assert result == expected_links
        mock_link_manager.list_links.assert_called_once_with(extract_dir, fork)

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_remove_release_success(self, mocker, tmp_path, fork, TEST_DATA):
        """Test remove_release method with successful removal using centralized test data."""
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

        # Use centralized test data for release tag
        release_tag = TEST_DATA["FORKS"][fork]["example_tag"]

        result = fetcher.remove_release(extract_dir, release_tag, fork)

        assert result is True
        mock_link_manager.remove_release.assert_called_once_with(
            extract_dir, release_tag, fork
        )

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_remove_release_not_found(self, mocker, tmp_path, fork):
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

        release_tag = "GE-Proton99-99" if fork == ForkName.GE_PROTON else "EM-10.0-99"

        with pytest.raises(LinkManagementError):
            fetcher.remove_release(extract_dir, release_tag, fork)

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_list_recent_releases_success(self, mocker, fork):
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

        # Use appropriate expected releases based on fork
        if fork == ForkName.GE_PROTON:
            expected_releases = ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]
        else:
            expected_releases = ["EM-10.0-30", "EM-10.0-29", "EM-9.0-28"]

        mock_release_manager.list_recent_releases.return_value = expected_releases

        repo = (
            "GloriousEggroll/proton-ge-custom"
            if fork == ForkName.GE_PROTON
            else "Etaash-mathamsetty/Proton"
        )

        result = fetcher.list_recent_releases(repo)

        assert result == expected_releases
        mock_release_manager.list_recent_releases.assert_called_once_with(repo)

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_list_recent_releases_network_error(self, mocker, fork):
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

        repo = (
            "GloriousEggroll/proton-ge-custom"
            if fork == ForkName.GE_PROTON
            else "Etaash-mathamsetty/Proton"
        )

        with pytest.raises(NetworkError):
            fetcher.list_recent_releases(repo)

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

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_determine_release_tag_latest(self, mocker, fork):
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

        if fork == ForkName.GE_PROTON:
            expected_tag = "GE-Proton10-20"
            repo = "GloriousEggroll/proton-ge-custom"
        else:
            expected_tag = "EM-10.0-30"
            repo = "Etaash-mathamsetty/Proton"

        mock_release_manager.fetch_latest_tag.return_value = expected_tag

        result = fetcher._determine_release_tag(
            repo=repo,
            manual_release_tag=None,
            fork=fork,
        )

        assert result == expected_tag
        mock_release_manager.fetch_latest_tag.assert_called_once_with(repo)

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_determine_release_tag_manual(self, mocker, fork):
        """Test _determine_release_tag method with manual tag."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        if fork == ForkName.GE_PROTON:
            manual_tag = "GE-Proton10-20"
            repo = "GloriousEggroll/proton-ge-custom"
        else:
            manual_tag = "EM-10.0-30"
            repo = "Etaash-mathamsetty/Proton"

        result = fetcher._determine_release_tag(
            repo=repo, release_tag=manual_tag, fork=fork
        )

        assert result == manual_tag
        # Should not call fetch_latest_tag since manual tag was provided


class TestGitHubReleaseFetcherInternalMethods:
    """Tests for GitHubReleaseFetcher internal methods."""

    @pytest.mark.parametrize(
        "fork,release_tag,expected_manual_dir",
        [
            (ForkName.GE_PROTON, "GE-Proton10-20", None),
            (ForkName.PROTON_EM, "EM-10.0-30", "proton-EM-10.0-30"),
        ],
    )
    def test_get_expected_directories(
        self, mocker, tmp_path, fork, release_tag, expected_manual_dir
    ):
        """Test _get_expected_directories returns correct paths for different forks."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        repo_dir, manual_dir = fetcher._get_expected_directories(
            tmp_path, release_tag, fork
        )

        assert repo_dir == tmp_path / release_tag
        # For GE-Proton, manual_dir should be None; for Proton-EM, it should have the "proton-" prefix
        assert manual_dir == (
            tmp_path / expected_manual_dir if expected_manual_dir else None
        )

    def test_get_expected_directories_manual_release_ge_proton(self, mocker, tmp_path):
        """Test _get_expected_directories with manual release tag for GE-Proton."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        repo_dir, manual_dir = fetcher._get_expected_directories(
            tmp_path, "manual-tag", ForkName.GE_PROTON
        )

        assert repo_dir == tmp_path / "manual-tag"
        assert manual_dir is None

    def test_handle_existing_directory_extract_success(self, mocker, tmp_path):
        """Test _handle_existing_directory returns existing directory when extract_dir exists."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
        )

        # Mock the link manager to prevent actual link management calls
        fetcher.link_manager = mock_link_manager
        mock_link_manager.manage_proton_links.return_value = True

        actual_dir = tmp_path / "GE-Proton10-20"

        def mock_exists(path):
            return path == actual_dir

        # Use mocker.patch.object to avoid lint errors
        mocker.patch.object(
            fetcher.file_system_client, "exists", side_effect=mock_exists
        )
        mocker.patch.object(fetcher.file_system_client, "is_dir", return_value=True)

        result = fetcher._handle_existing_directory(
            tmp_path, "GE-Proton10-20", ForkName.GE_PROTON, actual_dir, False
        )

        assert result == (True, actual_dir)

    def test_handle_existing_directory_manual_success(self, mocker, tmp_path):
        """Test _handle_existing_directory returns existing manual directory."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
        )

        # Mock the link manager to prevent actual link management calls
        fetcher.link_manager = mock_link_manager
        mock_link_manager.manage_proton_links.return_value = True

        actual_dir = tmp_path / "GE-Proton10-20"

        # Mock the filesystem client methods
        mocker.patch.object(
            fetcher.file_system_client,
            "exists",
            side_effect=lambda p: p == actual_dir,
        )
        mocker.patch.object(fetcher.file_system_client, "is_dir", return_value=True)

        result = fetcher._handle_existing_directory(
            tmp_path, "GE-Proton10-20", ForkName.GE_PROTON, actual_dir, True
        )

        assert result == (True, actual_dir)

    def test_handle_existing_directory_not_found(self, mocker, tmp_path):
        """Test _handle_existing_directory returns (False, None) when no directory exists."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
        )

        # Mock the link manager to prevent actual link management calls
        fetcher.link_manager = mock_link_manager
        mock_link_manager.manage_proton_links.return_value = True

        # Mock filesystem to report no directory exists
        actual_dir = tmp_path / "GE-Proton10-20"

        # Fix: Use mocker.patch.object instead of direct assignment
        mocker.patch.object(fetcher.file_system_client, "exists", return_value=False)

        result = fetcher._handle_existing_directory(
            tmp_path,  # extract_dir
            "GE-Proton10-20",  # release_tag
            ForkName.GE_PROTON,  # fork
            actual_dir,  # actual_directory
            False,  # is_manual_release
        )

        assert result == (False, None)


class TestGitHubReleaseFetcherBranchCoverage:
    """Branch-specific tests for GitHubReleaseFetcher to extend code coverage."""

    def test_ensure_directory_is_writable_mkdir_oserror(self, mocker):
        """Test _ensure_directory_is_writable when mkdir raises OSError."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        # Mock exists to return False (directory doesn't exist)
        mock_fs.exists.return_value = False
        # Mock mkdir to raise OSError
        mock_fs.mkdir.side_effect = OSError("Permission denied")

        directory = Path("/test/directory")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "Failed to create directory" in str(exc_info.value)
        # Verify mkdir was called with the test directory (second call)
        assert any(call[0][0] == directory for call in mock_fs.mkdir.call_args_list)

    def test_ensure_directory_is_writable_exists_but_not_dir(self, mocker):
        """Test _ensure_directory_is_writable when path exists but is not a directory."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        # Mock exists to return True, is_dir to return False
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = False

        directory = Path("/test/file")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "exists but is not a directory" in str(exc_info.value)

    def test_ensure_directory_is_writable_write_fails(self, mocker):
        """Test _ensure_directory_is_writable when write test fails."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        # Mock exists and is_dir to return True (directory exists and is dir)
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True
        # Mock write to raise OSError
        mock_fs.write.side_effect = OSError("Permission denied")

        directory = Path("/readonly/directory")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "is not writable" in str(exc_info.value)

    def test_ensure_directory_is_writable_unlink_fails(self, mocker):
        """Test _ensure_directory_is_writable when unlink test file fails."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        # Mock exists and is_dir to return True
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True
        # Mock write to succeed, but unlink to fail
        mock_fs.write.return_value = None
        mock_fs.unlink.side_effect = OSError("Permission denied")

        directory = Path("/problematic/directory")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "is not writable" in str(exc_info.value)

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_get_expected_directories_fork_specific(self, mocker, fork):
        """Test _get_expected_directories returns correct paths for different forks."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        extract_dir = Path("/test/extract")
        release_tag = "GE-Proton10-20" if fork == ForkName.GE_PROTON else "EM-10.0-30"

        repo_dir, manual_dir = fetcher._get_expected_directories(
            extract_dir, release_tag, fork
        )

        assert repo_dir == extract_dir / release_tag

        if fork == ForkName.PROTON_EM:
            expected_manual_dir = extract_dir / f"proton-{release_tag}"
            assert manual_dir == expected_manual_dir
        else:
            assert manual_dir is None

    def test_check_existing_directory_proton_em_both_exist(self, mocker, tmp_path):
        """Test _check_existing_directory when both Proton-EM directory formats exist."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        # Create test directories
        unpacked = tmp_path / "EM-10.0-30"
        unpacked_for_em = tmp_path / "proton-EM-10.0-30"
        unpacked.mkdir()
        unpacked_for_em.mkdir()

        # Test when both exist - should prefer the "proton-" prefixed one
        directory_exists, actual_directory = fetcher._check_existing_directory(
            unpacked, unpacked_for_em, ForkName.PROTON_EM
        )

        assert directory_exists is True
        assert actual_directory == unpacked_for_em

    def test_check_existing_directory_proton_em_only_tag_exists(self, mocker, tmp_path):
        """Test _check_existing_directory when only tag-named Proton-EM directory exists."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        # Create only the tag-named directory
        unpacked = tmp_path / "EM-10.0-30"
        unpacked.mkdir()
        unpacked_for_em = tmp_path / "proton-EM-10.0-30"

        directory_exists, actual_directory = fetcher._check_existing_directory(
            unpacked, unpacked_for_em, ForkName.PROTON_EM
        )

        assert directory_exists is True
        assert actual_directory == unpacked

    def test_check_existing_directory_ge_proton_only(self, mocker, tmp_path):
        """Test _check_existing_directory for GE-Proton when directory exists."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        # Create GE-Proton directory
        unpacked = tmp_path / "GE-Proton10-20"
        unpacked.mkdir()

        directory_exists, actual_directory = fetcher._check_existing_directory(
            unpacked, None, ForkName.GE_PROTON
        )

        assert directory_exists is True
        assert actual_directory == unpacked

    def test_check_existing_directory_none_exist(self, mocker, tmp_path):
        """Test _check_existing_directory when no directories exist."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        unpacked = tmp_path / "nonexistent"
        unpacked_for_em = tmp_path / "proton-nonexistent"

        directory_exists, actual_directory = fetcher._check_existing_directory(
            unpacked, unpacked_for_em, ForkName.PROTON_EM
        )

        assert directory_exists is False
        assert actual_directory is None

    def test_handle_existing_directory_not_found(self, mocker, tmp_path):
        """Test _handle_existing_directory when directory doesn't exist."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager

        actual_directory = tmp_path / "nonexistent"

        # Mock exists to return False
        mock_fs.exists.return_value = False

        result = fetcher._handle_existing_directory(
            tmp_path, "test-tag", ForkName.GE_PROTON, actual_directory, False
        )

        assert result == (False, None)
        mock_link_manager.manage_proton_links.assert_not_called()

    def test_download_asset_finds_asset_by_name_error(self, mocker, tmp_path):
        """Test _download_asset when find_asset_by_name raises ProtonFetcherError."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        # Mock release_manager to raise error
        mock_release_manager = mocker.Mock()
        mock_release_manager.find_asset_by_name.side_effect = ProtonFetcherError(
            "Asset not found"
        )
        fetcher.release_manager = mock_release_manager

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._download_asset(
                "test/repo", "test-tag", ForkName.GE_PROTON, tmp_path
            )

        assert "Could not find asset for release test-tag in test/repo" in str(
            exc_info.value
        )

    def test_download_asset_none_asset_name(self, mocker, tmp_path):
        """Test _download_asset when asset_name is None."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )

        # Mock release_manager to return None
        mock_release_manager = mocker.Mock()
        mock_release_manager.find_asset_by_name.return_value = None
        fetcher.release_manager = mock_release_manager

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._download_asset(
                "test/repo", "test-tag", ForkName.GE_PROTON, tmp_path
            )

        assert "Could not find asset for release test-tag in test/repo" in str(
            exc_info.value
        )

    def test_check_post_download_directory_exists(self, mocker, tmp_path):
        """Test _check_post_download_directory when directory exists after download."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager

        # Create directory that exists after download
        unpacked = tmp_path / "GE-Proton10-20"
        unpacked.mkdir()

        # Mock are_links_up_to_date to return False so manage_proton_links gets called
        mock_link_manager.are_links_up_to_date.return_value = False

        result = fetcher._check_post_download_directory(
            tmp_path, "GE-Proton10-20", ForkName.GE_PROTON, False
        )

        assert result == (True, unpacked)
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_check_post_download_directory_not_exists(self, mocker, tmp_path):
        """Test _check_post_download_directory when directory doesn't exist after download."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager

        result = fetcher._check_post_download_directory(
            tmp_path, "nonexistent", ForkName.GE_PROTON, False
        )

        assert result == (False, tmp_path)
        mock_link_manager.manage_proton_links.assert_not_called()

    def test_extract_and_manage_links_proton_em_fallback(self, mocker, tmp_path):
        """Test _extract_and_manage_links with Proton-EM fallback directory naming."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()
        mock_archive_extractor = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager
        fetcher.archive_extractor = mock_archive_extractor

        # Create the "proton-" prefixed directory that should be found as fallback
        proton_em_path = tmp_path / "proton-EM-10.0-30"
        proton_em_path.mkdir()

        archive_path = tmp_path / "test.tar.xz"
        archive_path.write_bytes(b"test")

        result = fetcher._extract_and_manage_links(
            archive_path, tmp_path, "EM-10.0-30", ForkName.PROTON_EM, False, True, True
        )

        assert result == proton_em_path
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_relink_fork_success(self, mocker, tmp_path):
        """Test relink_fork method successfully relinks symlinks."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager

        # Create test directory structure
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create version directories
        ge_proton10_20 = extract_dir / "GE-Proton10-20"
        ge_proton10_20.mkdir()
        ge_proton10_19 = extract_dir / "GE-Proton10-19"
        ge_proton10_19.mkdir()

        # Mock find_version_candidates to return our test directories
        mock_link_manager.find_version_candidates.return_value = [
            ((10, 20), ge_proton10_20),
            ((10, 19), ge_proton10_19),
        ]

        # Mock _deduplicate_candidates to return the same list
        mock_link_manager._deduplicate_candidates.return_value = [
            ((10, 20), ge_proton10_20),
            ((10, 19), ge_proton10_19),
        ]

        # Mock get_link_names_for_fork
        main_link = extract_dir / "GE-Proton"
        fb_link = extract_dir / "GE-Proton-Fallback"
        fb2_link = extract_dir / "GE-Proton-Fallback2"
        mock_link_manager.get_link_names_for_fork.return_value = (
            main_link,
            fb_link,
            fb2_link,
        )

        # Mock create_symlinks
        mock_link_manager.create_symlinks.return_value = True

        # Test relink_fork
        result = fetcher.relink_fork(extract_dir, ForkName.GE_PROTON)

        assert result is True
        mock_link_manager.find_version_candidates.assert_called_once_with(
            extract_dir, ForkName.GE_PROTON
        )
        mock_link_manager._deduplicate_candidates.assert_called_once()
        mock_link_manager.get_link_names_for_fork.assert_called_once_with(
            extract_dir, ForkName.GE_PROTON
        )
        mock_link_manager.create_symlinks.assert_called_once()

    def test_relink_fork_no_versions_found(self, mocker, tmp_path):
        """Test relink_fork method when no versions are found."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager

        # Create empty test directory
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Mock find_version_candidates to return empty list
        mock_link_manager.find_version_candidates.return_value = []

        # Test that relink_fork raises LinkManagementError
        with pytest.raises(LinkManagementError) as exc_info:
            fetcher.relink_fork(extract_dir, ForkName.GE_PROTON)

        assert "No valid GE-Proton versions found" in str(exc_info.value)
        mock_link_manager.find_version_candidates.assert_called_once_with(
            extract_dir, ForkName.GE_PROTON
        )
        mock_link_manager._deduplicate_candidates.assert_not_called()

    def test_extract_and_manage_links_no_fallback_found(self, mocker, tmp_path):
        """Test _extract_and_manage_links when no fallback directory is found."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()
        mock_archive_extractor = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager
        fetcher.archive_extractor = mock_archive_extractor

        archive_path = tmp_path / "test.tar.gz"
        archive_path.write_bytes(b"test")

        # Mock the archive extraction to create the expected directory structure
        def mock_extract(archive_path, target_dir, show_progress, show_file_details):
            unpacked_dir = target_dir / "GE-Proton10-20"
            unpacked_dir.mkdir()
            return target_dir

        mock_archive_extractor.extract_archive.side_effect = mock_extract

        result = fetcher._extract_and_manage_links(
            archive_path,
            tmp_path,
            "GE-Proton10-20",
            ForkName.GE_PROTON,
            False,
            True,
            True,
        )

        # Should return the unpacked directory when it's found
        assert result == tmp_path / "GE-Proton10-20"
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_fetch_and_extract_existing_directory_skip_processing(
        self, mocker, tmp_path
    ):
        """Test fetch_and_extract when existing directory causes skip_processing=True."""
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

        # Mock _check_existing_directory to return True (directory exists)
        mocker.patch.object(
            fetcher,
            "_check_existing_directory",
            return_value=(True, tmp_path / "extract" / "GE-Proton10-20"),
        )

        # Mock _handle_existing_directory to return skip_processing=True
        mocker.patch.object(
            fetcher,
            "_handle_existing_directory",
            return_value=(True, tmp_path / "extract" / "GE-Proton10-20"),
        )

        # Mock fetch_latest_tag to return a string instead of a Mock
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"

        result = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,
            fork=ForkName.GE_PROTON,
        )

        assert result == tmp_path / "extract" / "GE-Proton10-20"
        # Verify that download and extraction were NOT called due to skip_processing
        mock_asset_downloader.download_asset.assert_not_called()
        mock_archive_extractor.extract_archive.assert_not_called()

    def test_fetch_and_extract_post_download_skip_processing(self, mocker, tmp_path):
        """Test fetch_and_extract when post-download directory causes skip_processing=True."""
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

        # Mock _check_existing_directory to return False (no existing directory)
        mocker.patch.object(
            fetcher, "_check_existing_directory", return_value=(False, None)
        )

        # Mock _download_asset
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / "GE-Proton10-20.tar.gz"
        )

        # Mock _check_post_download_directory to return skip_processing=True
        mocker.patch.object(
            fetcher,
            "_check_post_download_directory",
            return_value=(True, tmp_path / "extract" / "GE-Proton10-20"),
        )

        result = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,
            fork=ForkName.GE_PROTON,
        )

        assert result == tmp_path / "extract" / "GE-Proton10-20"
        # Verify that extraction was NOT called due to skip_processing
        mock_archive_extractor.extract_archive.assert_not_called()

    def test_handle_existing_directory_skip_processing_true(self, mocker, tmp_path):
        """Test _handle_existing_directory when it returns skip_processing=True."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager

        actual_directory = tmp_path / "GE-Proton10-20"
        actual_directory.mkdir()

        # Mock exists to return True
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True

        # Mock are_links_up_to_date to return False so manage_proton_links gets called
        mock_link_manager.are_links_up_to_date.return_value = False

        result = fetcher._handle_existing_directory(
            tmp_path, "GE-Proton10-20", ForkName.GE_PROTON, actual_directory, False
        )

        assert result == (True, actual_directory)
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_check_post_download_directory_skip_processing_true(self, mocker, tmp_path):
        """Test _check_post_download_directory when it returns skip_processing=True."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager

        # Create directory that exists after download
        unpacked = tmp_path / "GE-Proton10-20"
        unpacked.mkdir()

        # Mock are_links_up_to_date to return False so manage_proton_links gets called
        mock_link_manager.are_links_up_to_date.return_value = False

        result = fetcher._check_post_download_directory(
            tmp_path, "GE-Proton10-20", ForkName.GE_PROTON, False
        )

        assert result == (True, unpacked)
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_extract_and_manage_links_skip_processing_true(self, mocker, tmp_path):
        """Test _extract_and_manage_links when directory exists after extraction."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()
        mock_archive_extractor = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager
        fetcher.archive_extractor = mock_archive_extractor

        # Create the directory that should be found after extraction
        proton_em_path = tmp_path / "proton-EM-10.0-30"
        proton_em_path.mkdir()

        archive_path = tmp_path / "test.tar.xz"
        archive_path.write_bytes(b"test")

        result = fetcher._extract_and_manage_links(
            archive_path, tmp_path, "EM-10.0-30", ForkName.PROTON_EM, False, True, True
        )

        assert result == proton_em_path
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_extract_and_manage_links_no_skip_processing(self, mocker, tmp_path):
        """Test _extract_and_manage_links when no directory exists after extraction."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()
        mock_archive_extractor = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager
        fetcher.archive_extractor = mock_archive_extractor

        archive_path = tmp_path / "test.tar.gz"
        archive_path.write_bytes(b"test")

        # Mock the archive extraction to create the expected directory structure
        def mock_extract(archive_path, target_dir, show_progress, show_file_details):
            unpacked_dir = target_dir / "GE-Proton10-20"
            unpacked_dir.mkdir()
            return target_dir

        mock_archive_extractor.extract_archive.side_effect = mock_extract

        result = fetcher._extract_and_manage_links(
            archive_path,
            tmp_path,
            "GE-Proton10-20",
            ForkName.GE_PROTON,
            False,
            True,
            True,
        )

        # Should return the unpacked directory when it's found
        assert result == tmp_path / "GE-Proton10-20"
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_fetch_and_extract_proton_em_fallback_directory(self, mocker, tmp_path):
        """Test fetch_and_extract with Proton-EM fallback directory naming."""
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

        # Mock _check_existing_directory to return False (no existing directory)
        mocker.patch.object(
            fetcher, "_check_existing_directory", return_value=(False, None)
        )

        # Mock _download_asset
        mock_release_manager.fetch_latest_tag.return_value = "EM-10.0-30"
        mock_release_manager.find_asset_by_name.return_value = "EM-10.0-30.tar.xz"
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / "EM-10.0-30.tar.xz"
        )

        # Mock _check_post_download_directory to return False (no directory found)
        mocker.patch.object(
            fetcher,
            "_check_post_download_directory",
            return_value=(False, tmp_path / "extract"),
        )

        # Create the "proton-" prefixed directory that should be found as fallback
        proton_em_path = tmp_path / "extract" / "proton-EM-10.0-30"
        proton_em_path.mkdir()

        result = fetcher.fetch_and_extract(
            repo="Etaash-mathamsetty/Proton",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,
            fork=ForkName.PROTON_EM,
        )

        assert result == proton_em_path
        mock_link_manager.manage_proton_links.assert_called_once()


class TestGitHubReleaseFetcherValidation:
    """Tests for GitHubReleaseFetcher directory validation methods."""

    def test_ensure_directory_is_writable_create_directory_fails(self, mocker):
        """Test _ensure_directory_is_writable when mkdir fails."""
        mock_network_client = mocker.Mock()
        mock_filesystem_client = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        # Make exists return False to trigger mkdir
        mock_filesystem_client.exists.return_value = False
        # Make mkdir raise OSError
        mock_filesystem_client.mkdir.side_effect = OSError("Permission denied")

        directory = Path("/nonexistent/directory")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "Failed to create directory" in str(exc_info.value)

    def test_ensure_directory_is_writable_dir_not_created(self, mocker):
        """Test _ensure_directory_is_writable when directory still doesn't exist after mkdir attempt."""
        mock_network_client = mocker.Mock()
        mock_filesystem_client = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        # First call to exists returns False, second returns False (still doesn't exist after mkdir)
        mock_filesystem_client.exists.side_effect = [
            False,
            False,
        ]  # First False triggers mkdir, second False triggers error

        directory = Path("/test/directory")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "does not exist and could not be created" in str(exc_info.value)

    def test_ensure_directory_is_writable_exists_but_not_dir(self, mocker):
        """Test _ensure_directory_is_writable when path exists but is not a directory."""
        mock_network_client = mocker.Mock()
        mock_filesystem_client = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        # Path exists but is_dir returns False
        mock_filesystem_client.exists.return_value = True
        mock_filesystem_client.is_dir.return_value = False

        directory = Path("/test/directory")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "exists but is not a directory" in str(exc_info.value)

    def test_ensure_directory_is_writable_not_writable_write_fails(self, mocker):
        """Test _ensure_directory_is_writable when directory is not writable."""
        mock_network_client = mocker.Mock()
        mock_filesystem_client = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        # Path exists and is a directory
        mock_filesystem_client.exists.return_value = True
        mock_filesystem_client.is_dir.return_value = True
        # Writing the test file fails
        mock_filesystem_client.write.side_effect = OSError("Permission denied")

        directory = Path("/readonly/directory")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "is not writable" in str(exc_info.value)

    def test_ensure_directory_is_writable_not_writable_unlink_fails(self, mocker):
        """Test _ensure_directory_is_writable when unlinking test file fails."""
        mock_network_client = mocker.Mock()
        mock_filesystem_client = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        # Path exists and is a directory
        mock_filesystem_client.exists.return_value = True
        mock_filesystem_client.is_dir.return_value = True

        # Writing succeeds, but unlinking fails
        def mock_write(path, data):
            pass  # Simulate successful write

        mock_filesystem_client.write.side_effect = mock_write
        mock_filesystem_client.unlink.side_effect = OSError("Permission denied")

        directory = Path("/readonly/directory")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "is not writable" in str(exc_info.value)

    def test_ensure_directory_is_writable_permission_error(self, mocker):
        """Test _ensure_directory_is_writable when operations raise PermissionError."""
        mock_network_client = mocker.Mock()
        mock_filesystem_client = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        # Make exists raise PermissionError
        mock_filesystem_client.exists.side_effect = PermissionError("Access denied")

        directory = Path("/protected/directory")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "Failed to create" in str(exc_info.value)

    def test_ensure_directory_is_writable_general_exception(self, mocker):
        """Test _ensure_directory_is_writable when operations raise general exceptions."""
        mock_network_client = mocker.Mock()
        mock_filesystem_client = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        # Make exists raise a general exception
        mock_filesystem_client.exists.side_effect = Exception("Unknown error")

        directory = Path("/problematic/directory")

        with pytest.raises(ProtonFetcherError) as exc_info:
            fetcher._ensure_directory_is_writable(directory)

        assert "Failed to create" in str(exc_info.value)

    def test_ensure_directory_is_writable_success(self, mocker):
        """Test _ensure_directory_is_writable successful case."""
        mock_network_client = mocker.Mock()
        mock_filesystem_client = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        # Set up successful case: directory exists and is writable
        mock_filesystem_client.exists.return_value = True
        mock_filesystem_client.is_dir.return_value = True

        directory = Path("/valid/directory")

        # Should not raise any exception
        fetcher._ensure_directory_is_writable(directory)

    def test_fetch_and_extract_existing_directory_skip_processing(
        self, mocker, tmp_path
    ):
        """Test fetch_and_extract when existing directory causes skip_processing=True."""
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

        # Mock _check_existing_directory to return True (directory exists)
        mocker.patch.object(
            fetcher,
            "_check_existing_directory",
            return_value=(True, tmp_path / "extract" / "GE-Proton10-20"),
        )

        # Mock _handle_existing_directory to return skip_processing=True
        mocker.patch.object(
            fetcher,
            "_handle_existing_directory",
            return_value=(True, tmp_path / "extract" / "GE-Proton10-20"),
        )

        # Mock fetch_latest_tag to return a string instead of a Mock
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"

        result = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,
            fork=ForkName.GE_PROTON,
        )

        assert result == tmp_path / "extract" / "GE-Proton10-20"
        # Verify that download and extraction were NOT called due to skip_processing
        mock_asset_downloader.download_asset.assert_not_called()
        mock_archive_extractor.extract_archive.assert_not_called()

    def test_fetch_and_extract_post_download_skip_processing(self, mocker, tmp_path):
        """Test fetch_and_extract when post-download directory causes skip_processing=True."""
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

        # Mock _check_existing_directory to return False (no existing directory)
        mocker.patch.object(
            fetcher, "_check_existing_directory", return_value=(False, None)
        )

        # Mock _download_asset
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / "GE-Proton10-20.tar.gz"
        )

        # Mock _check_post_download_directory to return skip_processing=True
        mocker.patch.object(
            fetcher,
            "_check_post_download_directory",
            return_value=(True, tmp_path / "extract" / "GE-Proton10-20"),
        )

        result = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,
            fork=ForkName.GE_PROTON,
        )

        assert result == tmp_path / "extract" / "GE-Proton10-20"
        # Verify that extraction was NOT called due to skip_processing
        mock_archive_extractor.extract_archive.assert_not_called()

    def test_handle_existing_directory_skip_processing_true(self, mocker, tmp_path):
        """Test _handle_existing_directory when it returns skip_processing=True."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager

        actual_directory = tmp_path / "GE-Proton10-20"
        actual_directory.mkdir()

        # Mock exists to return True
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True

        # Mock are_links_up_to_date to return False so manage_proton_links gets called
        mock_link_manager.are_links_up_to_date.return_value = False

        result = fetcher._handle_existing_directory(
            tmp_path, "GE-Proton10-20", ForkName.GE_PROTON, actual_directory, False
        )

        assert result == (True, actual_directory)
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_check_post_download_directory_skip_processing_true(self, mocker, tmp_path):
        """Test _check_post_download_directory when it returns skip_processing=True."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager

        # Create directory that exists after download
        unpacked = tmp_path / "GE-Proton10-20"
        unpacked.mkdir()

        # Mock are_links_up_to_date to return False so manage_proton_links gets called
        mock_link_manager.are_links_up_to_date.return_value = False

        result = fetcher._check_post_download_directory(
            tmp_path, "GE-Proton10-20", ForkName.GE_PROTON, False
        )

        assert result == (True, unpacked)
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_extract_and_manage_links_skip_processing_true(self, mocker, tmp_path):
        """Test _extract_and_manage_links when directory exists after extraction."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()
        mock_archive_extractor = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager
        fetcher.archive_extractor = mock_archive_extractor

        # Create the directory that should be found after extraction
        proton_em_path = tmp_path / "proton-EM-10.0-30"
        proton_em_path.mkdir()

        archive_path = tmp_path / "test.tar.xz"
        archive_path.write_bytes(b"test")

        result = fetcher._extract_and_manage_links(
            archive_path, tmp_path, "EM-10.0-30", ForkName.PROTON_EM, False, True, True
        )

        assert result == proton_em_path
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_extract_and_manage_links_no_skip_processing(self, mocker, tmp_path):
        """Test _extract_and_manage_links when no directory exists after extraction."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_link_manager = mocker.Mock()
        mock_archive_extractor = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs, timeout=60
        )
        fetcher.link_manager = mock_link_manager
        fetcher.archive_extractor = mock_archive_extractor

        archive_path = tmp_path / "test.tar.gz"
        archive_path.write_bytes(b"test")

        # Mock the archive extraction to create the expected directory structure
        def mock_extract(archive_path, target_dir, show_progress, show_file_details):
            unpacked_dir = target_dir / "GE-Proton10-20"
            unpacked_dir.mkdir()
            return target_dir

        mock_archive_extractor.extract_archive.side_effect = mock_extract

        result = fetcher._extract_and_manage_links(
            archive_path,
            tmp_path,
            "GE-Proton10-20",
            ForkName.GE_PROTON,
            False,
            True,
            True,
        )

        # Should return the unpacked directory when it's found
        assert result == tmp_path / "GE-Proton10-20"
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_fetch_and_extract_proton_em_fallback_directory(self, mocker, tmp_path):
        """Test fetch_and_extract with Proton-EM fallback directory naming."""
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

        # Mock _check_existing_directory to return False (no existing directory)
        mocker.patch.object(
            fetcher, "_check_existing_directory", return_value=(False, None)
        )

        # Mock _download_asset
        mock_release_manager.fetch_latest_tag.return_value = "EM-10.0-30"
        mock_release_manager.find_asset_by_name.return_value = (
            "proton-EM-10.0-30.tar.xz"
        )
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / "proton-EM-10.0-30.tar.xz"
        )

        # Mock _check_post_download_directory to return False (no directory after download)
        mocker.patch.object(
            fetcher,
            "_check_post_download_directory",
            return_value=(False, tmp_path / "extract"),
        )

        # Create the "proton-" prefixed directory that should be found as fallback
        proton_em_path = tmp_path / "extract" / "proton-EM-10.0-30"
        proton_em_path.mkdir()

        result = fetcher.fetch_and_extract(
            repo="Etaash-mathamsetty/Proton",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,
            fork=ForkName.PROTON_EM,
        )

        assert result == proton_em_path
        mock_link_manager.manage_proton_links.assert_called_once()
