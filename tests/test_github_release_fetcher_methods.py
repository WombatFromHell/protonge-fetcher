"""
Tests for GitHubReleaseFetcher methods in protonfetcher.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add the project directory to the Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from protonfetcher.common import ForkName  # noqa: E402
from protonfetcher.github_fetcher import GitHubReleaseFetcher  # noqa: E402


class TestGitHubReleaseFetcher:
    """Tests for GitHubReleaseFetcher methods."""

    def test_get_expected_directories_ge_proton(self, tmp_path):
        """Test _get_expected_directories returns correct paths for GE-Proton."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        repo_dir, manual_dir = fetcher._get_expected_directories(
            tmp_path, "GE-Proton10-20", ForkName.GE_PROTON
        )

        assert repo_dir == tmp_path / "GE-Proton10-20"
        # For GE-Proton, manual_dir should be None based on the function implementation
        assert manual_dir is None

    def test_get_expected_directories_proton_em(self, tmp_path):
        """Test _get_expected_directories returns correct paths for Proton-EM."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        repo_dir, manual_dir = fetcher._get_expected_directories(
            tmp_path, "EM-10.0-30", ForkName.PROTON_EM
        )

        # For Proton-EM: first value is extract_dir/release_tag, second is extract_dir/f"proton-{release_tag}"
        assert repo_dir == tmp_path / "EM-10.0-30"
        assert manual_dir == tmp_path / "proton-EM-10.0-30"

    def test_get_expected_directories_manual_release_ge_proton(self, tmp_path):
        """Test _get_expected_directories with manual release tag for GE-Proton."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

        repo_dir, manual_dir = fetcher._get_expected_directories(
            tmp_path, "manual-tag", ForkName.GE_PROTON
        )

        assert repo_dir == tmp_path / "manual-tag"
        assert manual_dir is None

    def test_handle_existing_directory_extract_success(
        self, tmp_path, mock_fetcher, mocker
    ):
        """Test _handle_existing_directory returns existing directory when extract_dir exists."""
        actual_dir = tmp_path / "GE-Proton10-20"

        def mock_exists(path):
            return path == actual_dir

        # Use mocker.patch.object to avoid lint errors
        mocker.patch.object(
            mock_fetcher.file_system_client, "exists", side_effect=mock_exists
        )
        mocker.patch.object(
            mock_fetcher.file_system_client, "is_dir", return_value=True
        )

        result = mock_fetcher._handle_existing_directory(
            tmp_path, "GE-Proton10-20", ForkName.GE_PROTON, actual_dir, False
        )

        assert result == (True, actual_dir)

    def test_handle_existing_directory_manual_success(
        self, tmp_path, mock_fetcher, mocker
    ):
        """Test _handle_existing_directory returns existing manual directory."""
        actual_dir = tmp_path / "GE-Proton10-20"

        # Mock the filesystem client methods
        mocker.patch.object(
            mock_fetcher.file_system_client,
            "exists",
            side_effect=lambda p: p == actual_dir,
        )
        mocker.patch.object(
            mock_fetcher.file_system_client, "is_dir", return_value=True
        )

        result = mock_fetcher._handle_existing_directory(
            tmp_path, "GE-Proton10-20", ForkName.GE_PROTON, actual_dir, True
        )

        assert result == (True, actual_dir)

    def test_handle_existing_directory_not_found(self, tmp_path, mocker):
        """Test _handle_existing_directory returns (False, None) when no directory exists."""
        mock_network = MagicMock()
        mock_fs = MagicMock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network, file_system_client=mock_fs
        )

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
