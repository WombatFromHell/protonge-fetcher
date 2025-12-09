"""
Parametrized error handling tests for all ProtonFetcher modules.
These tests ensure consistent error handling across different scenarios and forks.
"""

from pathlib import Path

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import ExtractionError, LinkManagementError, NetworkError
from protonfetcher.github_fetcher import GitHubReleaseFetcher


class TestErrorHandlingParametrized:
    """Parametrized tests for error handling across all modules."""

    @pytest.mark.parametrize(
        "fork,exception_type,error_message",
        [
            (ForkName.GE_PROTON, NetworkError, "Connection timeout"),
            (ForkName.PROTON_EM, NetworkError, "Connection timeout"),
            (ForkName.GE_PROTON, NetworkError, "SSL certificate error"),
            (ForkName.PROTON_EM, NetworkError, "SSL certificate error"),
            (ForkName.GE_PROTON, NetworkError, "DNS resolution failed"),
            (ForkName.PROTON_EM, NetworkError, "DNS resolution failed"),
        ],
    )
    def test_network_error_scenarios(self, mocker, fork, exception_type, error_message):
        """Test various network error scenarios across different forks."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock the release_manager to raise network error
        mock_release_manager = mocker.Mock()
        mock_release_manager.fetch_latest_tag.side_effect = exception_type(
            error_message
        )
        fetcher.release_manager = mock_release_manager

        repo = (
            "GloriousEggroll/proton-ge-custom"
            if fork == ForkName.GE_PROTON
            else "Etaash-mathamsetty/Proton"
        )

        with pytest.raises(exception_type):
            fetcher.fetch_and_extract(
                repo=repo,
                output_dir=Path("/tmp"),
                extract_dir=Path("/tmp"),
                release_tag=None,
                fork=fork,
            )

    @pytest.mark.parametrize(
        "fork,error_scenario",
        [
            (ForkName.GE_PROTON, "corrupted_archive"),
            (ForkName.PROTON_EM, "corrupted_archive"),
            (ForkName.GE_PROTON, "disk_full"),
            (ForkName.PROTON_EM, "disk_full"),
            (ForkName.GE_PROTON, "permissions_error"),
            (ForkName.PROTON_EM, "permissions_error"),
        ],
    )
    def test_extraction_error_scenarios(self, mocker, tmp_path, fork, error_scenario):
        """Test various extraction error scenarios across different forks."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Set up components
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Set up the scenario based on error type
        if fork == ForkName.GE_PROTON:
            release_tag = "GE-Proton10-20"
            asset_name = "GE-Proton10-20.tar.gz"
        else:
            release_tag = "EM-10.0-30"
            asset_name = "EM-10.0-30.tar.xz"

        mock_release_manager.fetch_latest_tag.return_value = release_tag
        mock_release_manager.find_asset_by_name.return_value = asset_name
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / asset_name
        )

        # Different extraction error scenarios
        if error_scenario == "corrupted_archive":
            mock_archive_extractor.extract_archive.side_effect = ExtractionError(
                "Archive is corrupted"
            )
        elif error_scenario == "disk_full":
            mock_archive_extractor.extract_archive.side_effect = ExtractionError(
                "Disk space exhausted"
            )
        elif error_scenario == "permissions_error":
            mock_archive_extractor.extract_archive.side_effect = ExtractionError(
                "Permission denied"
            )

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        repo = (
            "GloriousEggroll/proton-ge-custom"
            if fork == ForkName.GE_PROTON
            else "Etaash-mathamsetty/Proton"
        )

        with pytest.raises(ExtractionError):
            fetcher.fetch_and_extract(
                repo=repo,
                output_dir=tmp_path / "Downloads",
                extract_dir=tmp_path / "extract",
                release_tag=None,
                fork=fork,
            )

    @pytest.mark.parametrize(
        "fork,error_scenario",
        [
            (ForkName.GE_PROTON, "broken_symlink"),
            (ForkName.PROTON_EM, "broken_symlink"),
            (ForkName.GE_PROTON, "permission_denied"),
            (ForkName.PROTON_EM, "permission_denied"),
            (ForkName.GE_PROTON, "directory_not_found"),
            (ForkName.PROTON_EM, "directory_not_found"),
        ],
    )
    def test_link_management_error_scenarios(
        self, mocker, tmp_path, fork, error_scenario
    ):
        """Test various link management error scenarios across different forks."""
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

        # Set up all components
        mock_release_manager = mocker.Mock()
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Setup successful workflow until link management
        if fork == ForkName.GE_PROTON:
            release_tag = "GE-Proton10-20"
            asset_name = "GE-Proton10-20.tar.gz"
        else:
            release_tag = "EM-10.0-30"
            asset_name = "EM-10.0-30.tar.xz"

        mock_release_manager.fetch_latest_tag.return_value = release_tag
        mock_release_manager.find_asset_by_name.return_value = asset_name
        mock_asset_downloader.download_asset.return_value = (
            tmp_path / "Downloads" / asset_name
        )
        mock_archive_extractor.extract_archive.return_value = (
            tmp_path / "extract" / release_tag
        )

        # Mock the basic filesystem operations
        def mock_fs_exists(path):
            return str(path) in [str(tmp_path / "Downloads"), str(tmp_path / "extract")]

        def mock_fs_is_dir(path):
            return str(path) in [str(tmp_path / "Downloads"), str(tmp_path / "extract")]

        def mock_fs_mkdir(path, parents=False, exist_ok=False):
            pass

        def mock_fs_write(path, data):
            pass

        def mock_fs_unlink(path):
            pass

        mock_fs.exists.side_effect = mock_fs_exists
        mock_fs.is_dir.side_effect = mock_fs_is_dir
        mock_fs.mkdir.side_effect = mock_fs_mkdir
        mock_fs.write.side_effect = mock_fs_write
        mock_fs.unlink.side_effect = mock_fs_unlink

        # Different link management error scenarios
        if error_scenario == "broken_symlink":
            mock_link_manager.manage_proton_links.side_effect = LinkManagementError(
                "Broken symlink detected"
            )
        elif error_scenario == "permission_denied":
            mock_link_manager.manage_proton_links.side_effect = LinkManagementError(
                "Permission denied"
            )
        elif error_scenario == "directory_not_found":
            mock_link_manager.manage_proton_links.side_effect = LinkManagementError(
                "Directory not found"
            )

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        repo = (
            "GloriousEggroll/proton-ge-custom"
            if fork == ForkName.GE_PROTON
            else "Etaash-mathamsetty/Proton"
        )

        with pytest.raises(LinkManagementError):
            fetcher.fetch_and_extract(
                repo=repo,
                output_dir=tmp_path / "Downloads",
                extract_dir=tmp_path / "extract",
                release_tag=None,
                fork=fork,
            )

    @pytest.mark.parametrize(
        "fork,operation,method_name",
        [
            (ForkName.GE_PROTON, "fetch_and_extract", "fetch_and_extract"),
            (ForkName.PROTON_EM, "fetch_and_extract", "fetch_and_extract"),
            (ForkName.GE_PROTON, "list_links", "list_links"),
            (ForkName.PROTON_EM, "list_links", "list_links"),
            (ForkName.GE_PROTON, "remove_release", "remove_release"),
            (ForkName.PROTON_EM, "remove_release", "remove_release"),
        ],
    )
    def test_operation_error_propagation(
        self, mocker, tmp_path, fork, operation, method_name
    ):
        """Test that errors are properly propagated through different operations."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock the appropriate manager based on operation
        if operation == "fetch_and_extract":
            mock_release_manager = mocker.Mock()
            mock_release_manager.fetch_latest_tag.side_effect = NetworkError(
                "API error"
            )
            fetcher.release_manager = mock_release_manager

            repo = (
                "GloriousEggroll/proton-ge-custom"
                if fork == ForkName.GE_PROTON
                else "Etaash-mathamsetty/Proton"
            )

            with pytest.raises(NetworkError):
                fetcher.fetch_and_extract(
                    repo=repo,
                    output_dir=Path("/tmp"),
                    extract_dir=Path("/tmp"),
                    release_tag=None,
                    fork=fork,
                )
        elif operation == "list_links":
            mock_link_manager = mocker.Mock()
            mock_link_manager.list_links.side_effect = LinkManagementError(
                "Permission denied"
            )
            fetcher.link_manager = mock_link_manager

            extract_dir = tmp_path / "extract"
            extract_dir.mkdir()

            with pytest.raises(LinkManagementError):
                fetcher.list_links(extract_dir, fork)

        elif operation == "remove_release":
            mock_link_manager = mocker.Mock()
            mock_link_manager.remove_release.side_effect = LinkManagementError(
                "Directory not found"
            )
            fetcher.link_manager = mock_link_manager

            extract_dir = tmp_path / "extract"
            extract_dir.mkdir()

            release_tag = (
                "GE-Proton10-20" if fork == ForkName.GE_PROTON else "EM-10.0-30"
            )

            with pytest.raises(LinkManagementError):
                fetcher.remove_release(extract_dir, release_tag, fork)

    @pytest.mark.parametrize(
        "fork, asset_extension, error_type, error_message",
        [
            (ForkName.GE_PROTON, ".tar.gz", NetworkError, "Download failed"),
            (ForkName.PROTON_EM, ".tar.xz", NetworkError, "Download failed"),
            (ForkName.GE_PROTON, ".tar.gz", NetworkError, "Timeout"),
            (ForkName.PROTON_EM, ".tar.xz", NetworkError, "Connection refused"),
        ],
    )
    def test_asset_download_error_scenarios(
        self, mocker, tmp_path, fork, asset_extension, error_type, error_message
    ):
        """Test different asset download error scenarios."""
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
        mock_asset_downloader = mocker.Mock()
        mock_archive_extractor = mocker.Mock()
        mock_link_manager = mocker.Mock()

        fetcher.release_manager = mock_release_manager
        fetcher.asset_downloader = mock_asset_downloader
        fetcher.archive_extractor = mock_archive_extractor
        fetcher.link_manager = mock_link_manager

        # Set up successful initial steps
        if fork == ForkName.GE_PROTON:
            release_tag = "GE-Proton10-20"
            asset_name = f"GE-Proton10-20{asset_extension}"
        else:
            release_tag = "EM-10.0-30"
            asset_name = f"EM-10.0-30{asset_extension}"

        mock_release_manager.fetch_latest_tag.return_value = release_tag
        mock_release_manager.find_asset_by_name.return_value = asset_name
        mock_asset_downloader.download_asset.side_effect = error_type(error_message)

        # Create required directories
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        repo = (
            "GloriousEggroll/proton-ge-custom"
            if fork == ForkName.GE_PROTON
            else "Etaash-mathamsetty/Proton"
        )

        with pytest.raises(error_type):
            fetcher.fetch_and_extract(
                repo=repo,
                output_dir=tmp_path / "Downloads",
                extract_dir=tmp_path / "extract",
                release_tag=None,
                fork=fork,
            )
