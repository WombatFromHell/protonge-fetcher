"""
Parametrized tests for fork-specific functionality in protonfetcher.py
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

# Add the project directory to the Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from protonfetcher.common import ForkName  # noqa: E402
from protonfetcher.github_fetcher import GitHubReleaseFetcher  # noqa: E402


class TestForkParametrization:
    """Parametrized tests for different fork scenarios."""

    @pytest.mark.parametrize(
        "fork_name,expected_repo",
        [
            (ForkName.GE_PROTON, "GloriousEggroll/proton-ge-custom"),
            (ForkName.PROTON_EM, "Etaash-mathamsetty/Proton"),
        ],
    )
    def test_fetch_and_extract_different_forks(
        self, mocker: Any, tmp_path, fork_name, expected_repo
    ):
        """Test fetch_and_extract with different forks to ensure coverage."""
        # Mock all dependencies
        mock_network: Mock = mocker.Mock()
        mock_fs: Mock = mocker.Mock()
        mock_spinner: Mock = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock all sub-components
        mock_rm: Mock = mocker.Mock()
        mock_ad: Mock = mocker.Mock()
        mock_ae: Mock = mocker.Mock()
        mock_lm: Mock = mocker.Mock()

        fetcher.release_manager = mock_rm
        fetcher.asset_downloader = mock_ad
        fetcher.archive_extractor = mock_ae
        fetcher.link_manager = mock_lm

        # Set up mocks for successful workflow
        mock_rm.fetch_latest_tag.return_value = (
            "GE-Proton10-20" if fork_name == ForkName.GE_PROTON else "EM-10.0-30"
        )
        expected_asset = (
            "GE-Proton10-20.tar.gz"
            if fork_name == ForkName.GE_PROTON
            else "proton-EM-10.0-30.tar.xz"
        )
        mock_rm.find_asset_by_name.return_value = expected_asset
        mock_ad.download_asset.return_value = tmp_path / "Downloads" / expected_asset
        mock_ae.extract_archive.return_value = (
            tmp_path
            / "extract"
            / (
                "GE-Proton10-20"
                if fork_name == ForkName.GE_PROTON
                else "proton-EM-10.0-30"
            )
        )
        mock_lm.manage_proton_links.return_value = True

        # Mock filesystem operations for directory validation
        mocker.patch.object(fetcher.file_system_client, "exists", return_value=True)
        mocker.patch.object(fetcher.file_system_client, "is_dir", return_value=True)
        mocker.patch.object(fetcher.file_system_client, "mkdir", return_value=None)
        mocker.patch.object(fetcher.file_system_client, "write", return_value=None)
        mocker.patch.object(fetcher.file_system_client, "unlink", return_value=None)

        # Ensure directories exist
        (tmp_path / "Downloads").mkdir(exist_ok=True)
        (tmp_path / "extract").mkdir(exist_ok=True)

        # Run test
        result = fetcher.fetch_and_extract(
            repo=expected_repo,
            output_dir=tmp_path / "Downloads",
            extract_dir=tmp_path / "extract",
            release_tag=None,
            fork=fork_name,
        )

        # Verify correct operations were called
        if fork_name == ForkName.GE_PROTON:
            assert "GE-Proton" in str(result)
        else:
            assert "EM" in str(result) or "EM-" in str(result)

        # Verify all methods were called
        mock_rm.fetch_latest_tag.assert_called_once()
        mock_rm.find_asset_by_name.assert_called_once()
        mock_ad.download_asset.assert_called_once()
        mock_ae.extract_archive.assert_called_once()
        mock_lm.manage_proton_links.assert_called_once()

    @pytest.mark.parametrize(
        "fork,tag,expected_asset",
        [
            (ForkName.GE_PROTON, "GE-Proton10-20", "GE-Proton10-20.tar.gz"),
            (ForkName.PROTON_EM, "EM-10.0-30", "proton-EM-10.0-30.tar.xz"),
            (ForkName.GE_PROTON, "GE-Proton9-15", "GE-Proton9-15.tar.gz"),
            (ForkName.PROTON_EM, "EM-9.5-25", "proton-EM-9.5-25.tar.xz"),
        ],
    )
    def test_list_recent_releases_parametrized(
        self, mocker: Any, fork, tag, expected_asset
    ):
        """Test list_recent_releases with different fork/tag combinations."""
        mock_network: Mock = mocker.Mock()
        mock_fs: Mock = mocker.Mock()
        mock_spinner: Mock = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner,
            timeout=60,
        )

        # Mock the release_manager
        mock_rm: Mock = mocker.Mock()
        fetcher.release_manager = mock_rm

        expected_releases = [
            tag,
            tag.replace("10", "9") if "10" in tag else tag.replace("9", "8"),
        ]
        mock_rm.list_recent_releases.return_value = expected_releases

        repo = (
            "GloriousEggroll/proton-ge-custom"
            if fork == ForkName.GE_PROTON
            else "Etaash-mathamsetty/Proton"
        )
        result = fetcher.list_recent_releases(repo)

        assert result == expected_releases
        mock_rm.list_recent_releases.assert_called_once_with(repo)
