"""
Error handling tests for protonfetcher module.
Consolidating all error scenarios from various test files.
"""

import subprocess

import pytest

from protonfetcher.archive_extractor import ArchiveExtractor
from protonfetcher.common import ForkName
from protonfetcher.exceptions import ExtractionError, NetworkError, ProtonFetcherError
from protonfetcher.github_fetcher import GitHubReleaseFetcher
from protonfetcher.release_manager import ReleaseManager


class TestNetworkErrors:
    """Tests for network error conditions."""

    def test_fetch_latest_tag_network_error(self, mocker):
        """Test fetching latest tag with network error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock a failed response
        mock_network.head.side_effect = Exception("Network error")

        with pytest.raises(NetworkError):
            manager.fetch_latest_tag("test/repo")

    def test_get_remote_asset_size_not_found(self, mocker):
        """Test getting remote asset size with 404 error."""
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        manager = ReleaseManager(mock_network, mock_fs)

        # Mock response with 404 error
        mock_response = mocker.Mock()
        mock_response.returncode = 0  # return code 0 but contains 404 in stderr
        mock_response.stderr = "404 Not Found"
        mock_network.head.return_value = mock_response

        with pytest.raises(NetworkError):
            manager.get_remote_asset_size(
                "test/repo", "GE-Proton10-20", "GE-Proton10-20.tar.gz"
            )

    def test_cli_fetch_error_handling(self, mocker, tmp_path, capsys):
        """Test CLI error handling when fetch operation fails."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Make fetch_and_extract raise a ProtonFetcherError
        from protonfetcher.exceptions import ProtonFetcherError

        mock_fetcher.fetch_and_extract.side_effect = ProtonFetcherError(
            "Network error occurred"
        )

        test_args = [
            "protonfetcher",
            "-f",
            "GE-Proton",  # Add fork to trigger fetch operation
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Capture the SystemExit
        with pytest.raises(SystemExit) as exc_info:
            from protonfetcher.cli import main

            main()

        # Verify exit code is 1 for error
        assert exc_info.value.code == 1

        # Capture output to verify error message was printed
        captured = capsys.readouterr()
        assert "Error: Network error occurred" in captured.out


class TestExtractionErrors:
    """Tests for extraction error conditions."""

    def test_extraction_error_context(self, mocker, tmp_path):
        """Test that extraction errors include appropriate context."""
        from protonfetcher.filesystem import FileSystemClient

        # Create filesystem client
        file_system_client = FileSystemClient()

        # Create archive extractor
        extractor = ArchiveExtractor(file_system_client)

        # Create a corrupted archive file
        corrupted_archive_path = tmp_path / "corrupted.tar.gz"
        corrupted_archive_path.write_bytes(b"not a valid archive")

        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Try to extract the corrupted archive - should raise ExtractionError
        with pytest.raises(ExtractionError) as exc_info:
            extractor.extract_with_tarfile(corrupted_archive_path, target_dir)

        # Verify the error includes context about what went wrong
        error_str = str(exc_info.value)
        # The actual error message contains "Failed to read archive" which is what we expect
        assert (
            "Failed to read archive" in error_str
            or "Error reading archive" in error_str
        )

    def test_extraction_workflow_spinner_fallback(
        self, mocker, mock_network_client, mock_filesystem_client, tmp_path
    ):
        """Test download workflow when spinner fails and falls back to curl."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )
        output_path = tmp_path / "test.tar.gz"

        repo = "owner/repo"
        tag = "GE-Proton8-25"
        asset_name = "GE-Proton8-25.tar.gz"

        # Mock file system client to allow file operations
        mock_fs = mock_filesystem_client

        # Mock exists to return False initially (file doesn't exist before download)
        # but True after download for the specific path
        def mock_exists(path):
            # If it's the output path, return True after download would have happened
            if str(path) == str(output_path):
                return output_path.exists()
            return False

        mock_fs.exists.side_effect = mock_exists

        # Also need to mock the actual file creation/writing operations
        def mock_write(path, data):
            path.write_bytes(data)

        mock_fs.write = mock_write

        # Mock spinner download to fail
        mocker.patch.object(
            fetcher.asset_downloader,
            "download_with_spinner",
            side_effect=Exception("Network error"),
        )

        # Mock curl download to succeed - the actual download process should handle file creation
        # We need to make sure that when download_asset is called, the file ends up existing
        def mock_curl_download_func(url, output_path_param, headers=None):
            # Create the file to simulate successful download
            output_path_param.write_bytes(b"x" * 1024)  # Write 1KB of test data
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_curl_download = mocker.patch.object(
            fetcher.asset_downloader,
            "curl_download",
            side_effect=mock_curl_download_func,
        )

        # Mock size check
        mocker.patch.object(
            fetcher.release_manager, "get_remote_asset_size", return_value=1024
        )

        fetcher.asset_downloader.download_asset(
            repo, tag, asset_name, output_path, fetcher.release_manager
        )

        # Should have called curl download as fallback
        mock_curl_download.assert_called_once()


class TestLinkManagementErrors:
    """Tests for link management error conditions."""

    def test_cli_rm_flag_directory_not_found(self, mocker, tmp_path, capsys):
        """Test CLI command handles when the specified directory doesn't exist."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock the remove_release method to raise a ProtonFetcherError
        from protonfetcher.exceptions import ProtonFetcherError

        mock_fetcher.link_manager.remove_release.side_effect = ProtonFetcherError(
            "Release directory does not exist: /path/to/nonexistent"
        )

        test_args = [
            "protonfetcher",
            "--rm",
            "GE-Proton99-99",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Should exit with error code 1 due to the ProtonFetcherError
        with pytest.raises(SystemExit) as exc_info:
            from protonfetcher.cli import main

            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: Release directory does not exist:" in captured.out

    def test_remove_release_directory_not_found(
        self, mocker, mock_network_client, mock_filesystem_client, tmp_path
    ):
        """Test remove_release method when the specified directory doesn't exist."""
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Try to remove a directory that doesn't exist
        non_existent_tag = "GE-Proton99-99"
        _non_existent_dir = extract_dir / non_existent_tag

        # Mock file system operations
        mock_fs = mock_filesystem_client
        # Mock exists to return False for all checked paths
        mock_fs.exists = mocker.Mock(return_value=False)

        # Call the remove method, which should raise ProtonFetcherError
        with pytest.raises(
            ProtonFetcherError, match="Release directory does not exist"
        ):
            fetcher.link_manager.remove_release(
                extract_dir, non_existent_tag, ForkName.GE_PROTON
            )


class TestValidationErrors:
    """Tests for validation error conditions."""

    def test_cli_argument_validation(self, mocker, tmp_path, capsys):
        """Test CLI argument validation."""
        # Test with invalid fork choice
        test_args = [
            "protonfetcher",
            "-f",
            "Invalid-Fork",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Argparse will exit with code 2 for invalid argument
        with pytest.raises(SystemExit) as exc_info:
            from protonfetcher.cli import main

            main()

        # argparse exits with code 2 for argument errors
        assert exc_info.value.code == 2
        capsys.readouterr()
        # Error message will contain info about invalid choice

    def test_cli_list_flag_with_rate_limit_error(self, mocker, tmp_path, capsys):
        """Test CLI command handles rate limit errors properly."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock the list_recent_releases method to raise a rate limit error
        from protonfetcher.exceptions import ProtonFetcherError

        mock_fetcher.release_manager.list_recent_releases.side_effect = ProtonFetcherError(
            "API rate limit exceeded. Please wait a few minutes before trying again."
        )

        test_args = [
            "protonfetcher",
            "--list",
            "-f",
            "GE-Proton",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Should exit with error code 1 due to the ProtonFetcherError
        with pytest.raises(SystemExit) as exc_info:
            from protonfetcher.cli import main

            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: API rate limit exceeded" in captured.out

    def test_cli_list_flag_json_parse_error(self, mocker, tmp_path, capsys):
        """Test CLI handles JSON parsing errors in list functionality."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock the list_recent_releases method to raise a JSON parsing error
        from protonfetcher.exceptions import ProtonFetcherError

        mock_fetcher.release_manager.list_recent_releases.side_effect = ProtonFetcherError(
            "Failed to parse JSON response: Expecting value: line 1 column 1 (char 0)"
        )

        test_args = [
            "protonfetcher",
            "--list",
            "-f",
            "GE-Proton",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Should exit with error code 1 due to the JSON parse error
        with pytest.raises(SystemExit) as exc_info:
            from protonfetcher.cli import main

            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: Failed to parse JSON response" in captured.out

    def test_cli_list_flag_mixed_with_release_error(self, mocker, tmp_path, capsys):
        """Test that --list and --release cannot be used together."""
        # Don't even set up mocks since this should fail before calling any methods
        test_args = [
            "protonfetcher",
            "--list",
            "-r",
            "GE-Proton10-11",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Should exit with error code 1 due to argument validation
        with pytest.raises(SystemExit) as exc_info:
            from protonfetcher.cli import main

            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: --list and --release cannot be used together" in captured.out
