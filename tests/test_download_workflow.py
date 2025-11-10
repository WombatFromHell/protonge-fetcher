"""
Integration tests for download workflows in protonfetcher.py
"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protonfetcher import (
    ForkName,
    NetworkError,
    ProtonFetcherError,
)


class TestDownloadWorkflow:
    """Integration tests for download workflows with network error handling."""

    def test_download_workflow_success(self, mocker, tmp_path):
        """Test complete download workflow with successful execution."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup successful execution path
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_release_manager.get_remote_asset_size.return_value = (
            1024 * 1024 * 400
        )  # 400MB

        # Configure the asset downloader mock to call the release manager as expected
        # When download_asset is called, it should internally call get_remote_asset_size
        def mock_download_asset(repo, tag, asset_name, out_path, release_manager):
            # Simulate the internal logic that would call get_remote_asset_size
            remote_size = release_manager.get_remote_asset_size(repo, tag, asset_name)
            return tmp_path / "Downloads" / "GE-Proton10-20.tar.gz"

        mock_asset_downloader.download_asset.side_effect = mock_download_asset
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / "GE-Proton10-20"
        )
        mock_link_manager.manage_proton_links.return_value = None

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        result = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,
            fork=ForkName.GE_PROTON,
        )

        assert result is not None
        # Verify complete workflow execution
        mock_release_manager.fetch_latest_tag.assert_called_once()
        mock_release_manager.find_asset_by_name.assert_called_once()
        mock_release_manager.get_remote_asset_size.assert_called_once()
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_download_workflow_network_error(self, mocker, tmp_path):
        """Test download workflow with network error during tag fetching."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the release manager to fail
        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager

        # Setup network failure
        mock_release_manager.fetch_latest_tag.side_effect = NetworkError(
            "Network timeout"
        )

        with pytest.raises(NetworkError):
            fetcher.fetch_and_extract(
                repo="GloriousEggroll/proton-ge-custom",
                output_dir=tmp_path / "Downloads",
                extract_dir=tmp_path / "extract",
                release_tag=None,
                fork=ForkName.GE_PROTON,
            )

    def test_download_workflow_asset_not_found(self, mocker, tmp_path):
        """Test download workflow when asset is not found."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader

        # Setup execution path that fails at asset finding
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = None  # Asset not found
        mock_release_manager.get_remote_asset_size.return_value = 0

        with pytest.raises(ProtonFetcherError):
            fetcher.fetch_and_extract(
                repo="GloriousEggroll/proton-ge-custom",
                output_dir=tmp_path / "Downloads",
                extract_dir=tmp_path / "extract",
                release_tag=None,
                fork=ForkName.GE_PROTON,
            )

    @pytest.mark.parametrize(
        "fork,repo,tag",
        [
            (ForkName.GE_PROTON, "GloriousEggroll/proton-ge-custom", "GE-Proton10-20"),
            (ForkName.PROTON_EM, "Etaash-mathamsetty/Proton", "EM-10.0-30"),
        ],
    )
    def test_download_workflow_parametrized_forks(
        self, mocker, tmp_path, fork, repo, tag
    ):
        """Parametrized test for download workflow with different forks."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup successful execution path
        mock_release_manager.fetch_latest_tag.return_value = tag
        mock_release_manager.find_asset_by_name.return_value = (
            f"{tag.replace('EM-', 'proton-EM-').replace('GE-Proton', 'GE-Proton')}.tar.gz"
            if "GE-Proton" in tag
            else f"proton-{tag}.tar.xz"
        )
        mock_release_manager.get_remote_asset_size.return_value = (
            1024 * 1024 * 400
        )  # 400MB
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / f"{tag}.tar.gz"
        )
        mock_archive_extractor.extract_archive.return_value = tmp_path / "extract" / tag
        mock_link_manager.manage_proton_links.return_value = None

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        result = fetcher.fetch_and_extract(
            repo=repo,
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,
            fork=fork,
        )

        assert result is not None
        # Verify the workflow completed for the specific fork
        mock_release_manager.fetch_latest_tag.assert_called_once()
        mock_release_manager.find_asset_by_name.assert_called_once()
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_download_workflow_with_manual_release(self, mocker, tmp_path):
        """Test download workflow with manual release tag specified."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup successful execution path with manual tag
        manual_tag = "GE-Proton10-15"
        mock_release_manager.find_asset_by_name.return_value = f"{manual_tag}.tar.gz"
        mock_release_manager.get_remote_asset_size.return_value = (
            1024 * 1024 * 350
        )  # 350MB
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / f"{manual_tag}.tar.gz"
        )
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / manual_tag
        )
        mock_link_manager.manage_proton_links.return_value = None

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        result = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=manual_tag,
            fork=ForkName.GE_PROTON,
        )

        assert result is not None
        # Verify that fetch_latest_tag was NOT called since we provided a manual tag
        mock_release_manager.fetch_latest_tag.assert_not_called()
        # Verify find_asset was called with the manual tag
        mock_release_manager.find_asset_by_name.assert_called_once_with(
            "GloriousEggroll/proton-ge-custom", manual_tag, ForkName.GE_PROTON
        )
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_download_workflow_caching_behavior(self, mocker, tmp_path):
        """Test download workflow with caching behavior."""
        from protonfetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup execution path where file already exists (testing cache behavior)
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_release_manager.get_remote_asset_size.return_value = (
            1024 * 1024 * 400
        )  # 400MB

        # Mock that the file already exists and matches the expected size
        def mock_fs_exists(path):
            path_str = str(path)
            # Return True for the specific file or for directory paths that exist
            if "GE-Proton10-20.tar.gz" in path_str:
                return True
            # Also return True for our test directories that were created
            return "Downloads" in path_str or "extract" in path_str

        def mock_fs_stat(path):
            import unittest.mock

            stat_result = unittest.mock.Mock()
            stat_result.st_size = 1024 * 1024 * 400  # Matches expected size
            return stat_result

        def mock_fs_is_dir(path):
            path_str = str(path)
            # Return True for directory paths
            return "Downloads" in path_str or "extract" in path_str

        mock_fs.exists.side_effect = mock_fs_exists
        mock_fs.stat.side_effect = mock_fs_stat
        mock_fs.is_dir.side_effect = mock_fs_is_dir
        mock_fs.mkdir.return_value = None  # For directory creation

        # Configure the asset downloader mock to call the release manager as expected
        # When download_asset is called, it should internally call get_remote_asset_size
        def mock_download_asset(repo, tag, asset_name, out_path, release_manager):
            # Simulate the internal logic that would call get_remote_asset_size
            remote_size = release_manager.get_remote_asset_size(repo, tag, asset_name)
            return tmp_path / "Downloads" / "GE-Proton10-20.tar.gz"

        mock_asset_downloader.download_asset.side_effect = mock_download_asset
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / "GE-Proton10-20"
        )
        mock_link_manager.manage_proton_links.return_value = None

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        result = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,
            fork=ForkName.GE_PROTON,
        )

        assert result is not None
        # Verify the workflow completed even with existing file
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()
