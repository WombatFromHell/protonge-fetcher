"""
Integration tests for complete fetch-and-extract workflows in protonfetcher.py
"""

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import (
    ExtractionError,
    LinkManagementError,
    NetworkError,
    ProtonFetcherError,
)


class TestCompleteWorkflow:
    """Integration tests for full fetch-and-extract workflows with all components."""

    @pytest.mark.parametrize(
        "fork,expected_tag,expected_asset,expected_size,repo",
        [
            (
                ForkName.GE_PROTON,
                "GE-Proton10-20",
                "GE-Proton10-20.tar.gz",
                1024 * 1024 * 400,
                "GloriousEggroll/proton-ge-custom",
            ),
            (
                ForkName.PROTON_EM,
                "EM-10.0-30",
                "proton-EM-10.0-30.tar.xz",
                1024 * 1024 * 350,
                "Etaash-mathamsetty/Proton",
            ),
        ],
    )
    def test_complete_workflow_success(
        self, mocker, tmp_path, fork, expected_tag, expected_asset, expected_size, repo
    ):
        """Test complete workflow for both forks with successful execution."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock shutil.which to return curl path for validation (for GE-Proton)
        if fork == ForkName.GE_PROTON:
            mocker.patch("shutil.which", return_value="/usr/bin/curl")

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

        # Mock all internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup complete workflow based on fork
        mock_release_manager.fetch_latest_tag.return_value = expected_tag
        mock_release_manager.find_asset_by_name.return_value = expected_asset
        mock_release_manager.get_remote_asset_size.return_value = expected_size
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / expected_asset
        )
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / expected_tag
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

        mock_fs.exists.side_effect = mock_fs_exists
        mock_fs.is_dir.side_effect = mock_fs_is_dir
        mock_fs.mkdir.side_effect = mock_fs_mkdir
        mock_fs.write.side_effect = mock_fs_write
        mock_fs.unlink.side_effect = mock_fs_unlink

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

        assert result == tmp_path / "extract" / expected_tag
        # Verify all components were called in the complete workflow
        mock_release_manager.fetch_latest_tag.assert_called_once()
        mock_release_manager.find_asset_by_name.assert_called_once()
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_complete_workflow_manual_release_success(self, mocker, tmp_path):
        """Test complete workflow with manual release tag specified."""

        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock shutil.which to return curl path for validation
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

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

        # Mock all internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup complete workflow with manual tag
        manual_tag = "GE-Proton10-15"
        mock_release_manager.find_asset_by_name.return_value = f"{manual_tag}.tar.gz"
        mock_release_manager.get_remote_asset_size.return_value = (
            1024 * 1024 * 380
        )  # 380MB
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / f"{manual_tag}.tar.gz"
        )
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / manual_tag
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

        mock_fs.exists.side_effect = mock_fs_exists
        mock_fs.is_dir.side_effect = mock_fs_is_dir
        mock_fs.mkdir.side_effect = mock_fs_mkdir
        mock_fs.write.side_effect = mock_fs_write
        mock_fs.unlink.side_effect = mock_fs_unlink

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

        assert result == tmp_path / "extract" / manual_tag
        # Verify fetch_latest_tag was NOT called since we provided a manual tag
        mock_release_manager.fetch_latest_tag.assert_not_called()
        # Verify find_asset was called with the manual tag
        mock_release_manager.find_asset_by_name.assert_called_once_with(
            "GloriousEggroll/proton-ge-custom", manual_tag, ForkName.GE_PROTON
        )
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_complete_workflow_network_failure(self, mocker, tmp_path):
        """Test complete workflow with network failure."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

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

        # Mock the release manager to fail at network level
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

    def test_complete_workflow_extraction_failure(self, mocker, tmp_path):
        """Test complete workflow with extraction failure."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

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

        # Mock all internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor

        # Setup workflow that fails at extraction
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_release_manager.get_remote_asset_size.return_value = (
            1024 * 1024 * 400
        )  # 400MB
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / "GE-Proton10-20.tar.gz"
        )
        mock_archive_extractor.extract_archive.side_effect = ExtractionError(
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

    def test_complete_workflow_link_management_failure(self, mocker, tmp_path):
        """Test complete workflow with link management failure."""

        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock shutil.which to return curl path for validation
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

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

        # Mock all internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup workflow that fails at link management
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_release_manager.get_remote_asset_size.return_value = (
            1024 * 1024 * 400
        )  # 400MB
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

        mock_fs.exists.side_effect = mock_fs_exists
        mock_fs.is_dir.side_effect = mock_fs_is_dir
        mock_fs.mkdir.side_effect = mock_fs_mkdir
        mock_fs.write.side_effect = mock_fs_write
        mock_fs.unlink.side_effect = mock_fs_unlink

        mock_link_manager.manage_proton_links.side_effect = LinkManagementError(
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

    @pytest.mark.parametrize(
        "fork,repo,expected_asset_pattern",
        [
            (ForkName.GE_PROTON, "GloriousEggroll/proton-ge-custom", ".tar.gz"),
            (ForkName.PROTON_EM, "Etaash-mathamsetty/Proton", ".tar.xz"),
        ],
    )
    def test_complete_workflow_parametrized_forks(
        self, mocker, tmp_path, fork, repo, expected_asset_pattern
    ):
        """Parametrized test for complete workflow with different forks."""

        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock shutil.which to return curl path for validation
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

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

        # Mock all internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup appropriate values based on fork
        if fork == ForkName.GE_PROTON:
            tag = "GE-Proton10-20"
            asset_name = f"{tag}.tar.gz"
        else:  # Proton-EM
            tag = "EM-10.0-30"
            asset_name = f"proton-{tag}.tar.xz"

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

        mock_fs.exists.side_effect = mock_fs_exists
        mock_fs.is_dir.side_effect = mock_fs_is_dir
        mock_fs.mkdir.side_effect = mock_fs_mkdir
        mock_fs.write.side_effect = mock_fs_write
        mock_fs.unlink.side_effect = mock_fs_unlink

        # Setup complete workflow
        mock_release_manager.fetch_latest_tag.return_value = tag
        mock_release_manager.find_asset_by_name.return_value = asset_name
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / asset_name
        )
        mock_archive_extractor.extract_archive.return_value = tmp_path / "extract" / tag
        mock_link_manager.manage_proton_links.return_value = True

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
        # Verify all components were called
        mock_release_manager.fetch_latest_tag.assert_called_once()
        mock_release_manager.find_asset_by_name.assert_called_once()
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_complete_workflow_directory_validation_failure(self, mocker, tmp_path):
        """Test complete workflow with directory validation failure."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

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

        # Mock the _ensure_directory_is_writable to fail
        mocker.patch.object(
            fetcher,
            "_ensure_directory_is_writable",
            side_effect=ProtonFetcherError("Directory not writable"),
        )

        with pytest.raises(ProtonFetcherError):
            fetcher.fetch_and_extract(
                repo="GloriousEggroll/proton-ge-custom",
                output_dir=tmp_path / "Downloads",
                extract_dir=tmp_path / "non_writable_dir",
                release_tag=None,
                fork=ForkName.GE_PROTON,
            )

    def test_complete_workflow_with_caching_behavior(self, mocker, tmp_path):
        """Test complete workflow with caching behavior."""

        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock shutil.which to return curl path for validation
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

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

        # Mock all internal managers
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup workflow where asset already exists (testing caching)
        mock_release_manager.fetch_latest_tag.return_value = "GE-Proton10-20"
        mock_release_manager.find_asset_by_name.return_value = "GE-Proton10-20.tar.gz"
        mock_release_manager.get_remote_asset_size.return_value = (
            1024 * 1024 * 400
        )  # 400MB

        # Mock that the file already exists and download returns the existing file
        # Combined with the directory validation mocks below
        def mock_fs_exists_base(path):
            # Return True for download, extract directories AND for asset file for caching
            if str(path) in [str(tmp_path / "Downloads"), str(tmp_path / "extract")]:
                return True
            return "GE-Proton10-20.tar.gz" in str(path)

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

        def mock_fs_stat(path):
            stat_result = mocker.Mock()
            if "GE-Proton10-20.tar.gz" in str(path):
                stat_result.st_size = (
                    1024 * 1024 * 400
                )  # Matches expected size for caching
            else:
                stat_result.st_size = 0
            return stat_result

        mock_fs.exists.side_effect = mock_fs_exists_base
        mock_fs.is_dir.side_effect = mock_fs_is_dir
        mock_fs.mkdir.side_effect = mock_fs_mkdir
        mock_fs.write.side_effect = mock_fs_write
        mock_fs.unlink.side_effect = mock_fs_unlink
        mock_fs.stat.side_effect = mock_fs_stat

        existing_file_path = tmp_path / "Downloads" / "GE-Proton10-20.tar.gz"
        mock_asset_downloader.download_asset.return_value = existing_file_path
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / "GE-Proton10-20"
        )
        mock_link_manager.manage_proton_links.return_value = True

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

        assert result == tmp_path / "extract" / "GE-Proton10-20"
        # Verify the workflow completed with caching behavior
        mock_asset_downloader.download_asset.assert_called_once()
        mock_archive_extractor.extract_archive.assert_called_once()
        mock_link_manager.manage_proton_links.assert_called_once()

    def test_complete_workflow_asset_not_found(self, mocker, tmp_path):
        """Test complete workflow when asset is not found."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

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

        # Mock all internal managers
        mock_release_manager = mocker.Mock()
        fetcher.release_manager = mock_release_manager

        # Setup workflow where asset cannot be found
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
