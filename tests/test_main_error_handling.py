"""
Tests for main function error handling in protonfetcher.py
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from protonfetcher.cli import main
from protonfetcher.exceptions import ProtonFetcherError


class TestMainErrorHandling:
    """Tests for main function error handling paths."""

    def test_main_catches_proton_fetcher_error(self, tmp_path, capsys):
        """Test that main function catches ProtonFetcherError and exits with code 1."""
        # Create a fake arguments file to simulate command line args
        original_argv = sys.argv[:]

        try:
            # Simulate command line arguments that would trigger the default operation
            sys.argv = [
                "protonfetcher",
                "-x",
                str(tmp_path / "extract"),
                "-o",
                str(tmp_path / "download"),
            ]

            # Mock the GitHubReleaseFetcher to raise an exception during fetch_and_extract
            with patch("protonfetcher.cli.GitHubReleaseFetcher") as mock_fetcher_class:
                mock_fetcher_instance = MagicMock()
                mock_fetcher_instance.fetch_and_extract.side_effect = (
                    ProtonFetcherError("Test error")
                )
                mock_fetcher_class.return_value = mock_fetcher_instance

                # Mock _ensure_directory_is_writable to succeed
                with patch.object(
                    mock_fetcher_instance,
                    "_ensure_directory_is_writable",
                    return_value=None,
                ):
                    # Mock the fetch_and_extract method to raise an exception
                    with pytest.raises(SystemExit) as exc_info:
                        main()

                    # Verify that the exit code is 1
                    assert exc_info.value.code == 1

                    # Verify that the error message was printed
                    captured = capsys.readouterr()
                    assert "Error:" in captured.out or "Error:" in captured.err

        finally:
            # Restore original argv
            sys.argv = original_argv

    def test_main_with_ls_flag_error(self, tmp_path, capsys):
        """Test main function error handling with --ls flag."""
        original_argv = sys.argv[:]

        try:
            # Simulate --ls flag
            sys.argv = ["protonfetcher", "--ls", "-x", str(tmp_path / "extract")]

            with patch("protonfetcher.cli.GitHubReleaseFetcher") as mock_fetcher_class:
                mock_fetcher_instance = MagicMock()
                # Mock list_links to raise an exception
                mock_fetcher_instance.link_manager.list_links.side_effect = (
                    ProtonFetcherError("Test error for ls")
                )
                mock_fetcher_class.return_value = mock_fetcher_instance

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

                # Verify error message was printed
                captured = capsys.readouterr()
                assert "Error:" in captured.out or "Error:" in captured.err

        finally:
            sys.argv = original_argv

    def test_main_with_list_flag_error(self, tmp_path, capsys):
        """Test main function error handling with --list flag."""
        original_argv = sys.argv[:]

        try:
            # Simulate --list flag
            sys.argv = ["protonfetcher", "--list", "-f", "GE-Proton"]

            with patch("protonfetcher.cli.GitHubReleaseFetcher") as mock_fetcher_class:
                mock_fetcher_instance = MagicMock()
                # Mock list_recent_releases to raise an exception
                mock_fetcher_instance.release_manager.list_recent_releases.side_effect = ProtonFetcherError(
                    "Test error for list"
                )
                mock_fetcher_class.return_value = mock_fetcher_instance

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

                captured = capsys.readouterr()
                assert "Error:" in captured.out or "Error:" in captured.err

        finally:
            sys.argv = original_argv

    def test_main_with_rm_flag_error(self, tmp_path, capsys):
        """Test main function error handling with --rm flag."""
        original_argv = sys.argv[:]

        try:
            # Simulate --rm flag
            sys.argv = [
                "protonfetcher",
                "--rm",
                "test-tag",
                "-x",
                str(tmp_path / "extract"),
                "-f",
                "GE-Proton",
            ]

            with patch("protonfetcher.cli.GitHubReleaseFetcher") as mock_fetcher_class:
                mock_fetcher_instance = MagicMock()
                # Mock remove_release to raise an exception
                mock_fetcher_instance.link_manager.remove_release.side_effect = (
                    ProtonFetcherError("Test error for rm")
                )
                mock_fetcher_class.return_value = mock_fetcher_instance

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

                captured = capsys.readouterr()
                assert "Error:" in captured.out or "Error:" in captured.err

        finally:
            sys.argv = original_argv
