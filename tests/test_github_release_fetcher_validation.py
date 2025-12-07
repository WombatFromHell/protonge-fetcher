"""
Tests for GitHubReleaseFetcher _ensure_directory_is_writable functionality in protonfetcher.py
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from protonfetcher.exceptions import ProtonFetcherError
from protonfetcher.github_fetcher import GitHubReleaseFetcher


class TestGitHubReleaseFetcherDirectoryValidation:
    """Tests for GitHubReleaseFetcher directory validation methods."""

    def test_ensure_directory_is_writable_create_directory_fails(self):
        """Test _ensure_directory_is_writable when mkdir fails."""
        mock_network_client = MagicMock()
        mock_filesystem_client = MagicMock()

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

    def test_ensure_directory_is_writable_dir_not_created(self):
        """Test _ensure_directory_is_writable when directory still doesn't exist after mkdir attempt."""
        mock_network_client = MagicMock()
        mock_filesystem_client = MagicMock()

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

    def test_ensure_directory_is_writable_exists_but_not_dir(self):
        """Test _ensure_directory_is_writable when path exists but is not a directory."""
        mock_network_client = MagicMock()
        mock_filesystem_client = MagicMock()

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

    def test_ensure_directory_is_writable_not_writable_write_fails(self):
        """Test _ensure_directory_is_writable when directory is not writable."""
        mock_network_client = MagicMock()
        mock_filesystem_client = MagicMock()

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

    def test_ensure_directory_is_writable_not_writable_unlink_fails(self):
        """Test _ensure_directory_is_writable when unlinking test file fails."""
        mock_network_client = MagicMock()
        mock_filesystem_client = MagicMock()

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

    def test_ensure_directory_is_writable_permission_error(self):
        """Test _ensure_directory_is_writable when operations raise PermissionError."""
        mock_network_client = MagicMock()
        mock_filesystem_client = MagicMock()

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

    def test_ensure_directory_is_writable_general_exception(self):
        """Test _ensure_directory_is_writable when operations raise general exceptions."""
        mock_network_client = MagicMock()
        mock_filesystem_client = MagicMock()

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

    def test_ensure_directory_is_writable_success(self):
        """Test _ensure_directory_is_writable successful case."""
        mock_network_client = MagicMock()
        mock_filesystem_client = MagicMock()

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
