"""
Tests for CLI error handling in protonfetcher module.
Testing error scenarios and exception handling.
"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protonfetcher.cli import main
from protonfetcher.common import ForkName
from protonfetcher.exceptions import ProtonFetcherError


class TestCLIErrorHandling:
    """Tests for CLI error handling with different forks."""

    @pytest.mark.parametrize(
        "fork, error_scenario, expected_error_message",
        [
            (ForkName.GE_PROTON, "fetch_error", "Network error occurred"),
            (ForkName.PROTON_EM, "fetch_error", "Network error occurred"),
            (ForkName.GE_PROTON, "rate_limit", "API rate limit exceeded"),
            (ForkName.PROTON_EM, "rate_limit", "API rate limit exceeded"),
        ],
    )
    def test_cli_error_handling_parametrized(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
        capsys,
        fork,
        error_scenario,
        expected_error_message,
    ):
        """Parametrized test for CLI error handling with different forks."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Configure different error scenarios
        if error_scenario == "fetch_error":
            mock_fetcher.fetch_and_extract.side_effect = ProtonFetcherError(
                expected_error_message
            )
        elif error_scenario == "rate_limit":
            mock_fetcher.release_manager.list_recent_releases.side_effect = (
                ProtonFetcherError(expected_error_message)
            )

        # Test both fetch_and_extract and list_recent_releases depending on scenario
        test_args = ["protonfetcher", "-f", fork.value]

        if error_scenario == "rate_limit":
            test_args.insert(
                1, "--list"
            )  # Add list flag to trigger list_recent_releases

        test_args.extend(
            [
                "--extract-dir",
                str(tmp_path / "compatibilitytools.d"),
                "--output",
                str(tmp_path / "Downloads"),
            ]
        )
        mocker.patch("sys.argv", test_args)

        # Capture the SystemExit
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Verify exit code is 1 for error
        assert exc_info.value.code == 1

        # Capture output to verify error message was printed
        captured = capsys.readouterr()
        assert f"Error: {expected_error_message}" in captured.out

    def test_cli_fetch_error_handling(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI error handling when fetch operation fails."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Make fetch_and_extract raise a ProtonFetcherError
        mock_fetcher.fetch_and_extract.side_effect = ProtonFetcherError(
            "Network error occurred"
        )

        test_args = [
            "protonfetcher",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Capture the SystemExit
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Verify exit code is 1 for error
        assert exc_info.value.code == 1

        # Capture output to verify error message was printed
        captured = capsys.readouterr()
        assert "Error: Network error occurred" in captured.out

    def test_cli_argument_validation(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
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
            main()

        # argparse exits with code 2 for argument errors
        assert exc_info.value.code == 2
        capsys.readouterr()
        # Error message will contain info about invalid choice


class TestCLIArgumentValidation:
    """Tests for CLI argument validation and error handling."""

    def test_cli_invalid_fork_string_conversion(self, mocker, tmp_path, capsys):
        """Test when args.fork is an invalid string not in ForkName enum."""

        # Mock the GitHubReleaseFetcher to avoid actual operations
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Set up command line arguments with invalid fork
        test_args = [
            "protonfetcher",
            "-f",
            "InvalidForkName",  # Invalid fork name
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Try to run main - should raise SystemExit(2) from argparse validation
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Verify SystemExit was raised with correct code (argparse validation fails with code 2)
        assert exc_info.value.code == 2

    def test_cli_list_and_release_mutually_exclusive(self, mocker, tmp_path):
        """Test that --list and --release cannot be used together."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Set up command line arguments with both --list and --release
        test_args = [
            "protonfetcher",
            "-l",  # --list flag
            "-r",
            "GE-Proton8-25",  # --release flag
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Try to run main - should raise SystemExit(1) for mutually exclusive args
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Verify SystemExit was raised with correct code
        assert exc_info.value.code == 1

    def test_cli_ls_with_release_mutually_exclusive(self, mocker, tmp_path):
        """Test that --ls and --release cannot be used together."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Set up command line arguments with both --ls and --release
        test_args = [
            "protonfetcher",
            "--ls",  # --ls flag
            "-r",
            "GE-Proton8-25",  # --release flag
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    def test_cli_ls_with_list_mutually_exclusive(self, mocker, tmp_path):
        """Test that --ls and --list cannot be used together."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Set up command line arguments with both --ls and --list
        test_args = [
            "protonfetcher",
            "--ls",
            "-l",  # --list flag
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    def test_cli_rm_with_list_mutually_exclusive(self, mocker, tmp_path):
        """Test that --rm and --list cannot be used together."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Set up command line arguments with both --rm and --list
        test_args = [
            "protonfetcher",
            "--rm",
            "GE-Proton8-25",
            "-l",  # --list flag
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    def test_cli_rm_with_release_mutually_exclusive(self, mocker, tmp_path):
        """Test that --rm and --release cannot be used together (both need release tag)."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Even though both use a release tag, they have different meanings and are mutually exclusive
        test_args = [
            "protonfetcher",
            "--rm",
            "GE-Proton8-25",  # The release to remove
            "--release",
            "GE-Proton8-25",  # The release to fetch - this should be invalid
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    def test_cli_ls_with_ls_and_rm_mutually_exclusive(self, mocker, tmp_path):
        """Test that --ls and --rm cannot be used together."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Set up command line arguments with both --ls and --rm
        test_args = [
            "protonfetcher",
            "--ls",
            "--rm",
            "GE-Proton8-25",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    def test_cli_invalid_release_tag_format(self, mocker, tmp_path):
        """Test CLI with invalid release tag format."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Set up command line arguments with invalid release tag
        test_args = [
            "protonfetcher",
            "-f",
            "GE-Proton",
            "-r",
            "Invalid-Tag-Format",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # This should not cause a SystemExit from argument validation
        # but might cause an error during the fetch process
        try:
            main()
        except SystemExit as e:
            # May exit with code 1 if the invalid tag causes an error in processing
            if e.code == 1:
                pass  # This is acceptable
            else:
                raise


class TestCLIErrorHandlingWithForks:
    """Tests for CLI error handling with different fork-specific errors."""

    @pytest.mark.parametrize(
        "fork",
        [
            ForkName.GE_PROTON,
            ForkName.PROTON_EM,
        ],
    )
    def test_cli_network_error_handling_by_fork(
        self, mocker: MockerFixture, tmp_path: Path, capsys, fork
    ):
        """Test CLI network error handling for different forks."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Make fetch_and_extract raise a network error
        from protonfetcher.exceptions import NetworkError

        mock_fetcher.fetch_and_extract.side_effect = NetworkError("Connection timeout")

        test_args = [
            "protonfetcher",
            "-f",
            fork.value,
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Capture the SystemExit
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Verify exit code is 1 for error
        assert exc_info.value.code == 1

        # Capture output to verify error message was printed
        captured = capsys.readouterr()
        assert "Error: Connection timeout" in captured.out

    @pytest.mark.parametrize(
        "fork",
        [
            ForkName.GE_PROTON,
            ForkName.PROTON_EM,
        ],
    )
    def test_cli_extraction_error_handling_by_fork(
        self, mocker: MockerFixture, tmp_path: Path, capsys, fork
    ):
        """Test CLI extraction error handling for different forks."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Make fetch_and_extract raise an extraction error
        from protonfetcher.exceptions import ExtractionError

        mock_fetcher.fetch_and_extract.side_effect = ExtractionError(
            "Failed to extract archive"
        )

        test_args = [
            "protonfetcher",
            "-f",
            fork.value,
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Capture the SystemExit
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Verify exit code is 1 for error
        assert exc_info.value.code == 1

        # Capture output to verify error message was printed
        captured = capsys.readouterr()
        assert "Error: Failed to extract archive" in captured.out

    @pytest.mark.parametrize(
        "fork",
        [
            ForkName.GE_PROTON,
            ForkName.PROTON_EM,
        ],
    )
    def test_cli_link_management_error_handling_by_fork(
        self, mocker: MockerFixture, tmp_path: Path, capsys, fork
    ):
        """Test CLI link management error handling for different forks."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Make fetch_and_extract raise a link management error
        from protonfetcher.exceptions import LinkManagementError

        mock_fetcher.fetch_and_extract.side_effect = LinkManagementError(
            "Failed to create symbolic links"
        )

        test_args = [
            "protonfetcher",
            "-f",
            fork.value,
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Capture the SystemExit
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Verify exit code is 1 for error
        assert exc_info.value.code == 1

        # Capture output to verify error message was printed
        captured = capsys.readouterr()
        assert "Error: Failed to create symbolic links" in captured.out


class TestCLIErrorHandlingSpecialScenarios:
    """Tests for CLI error handling in special scenarios."""

    def test_cli_directory_not_writable_error(self, mocker, tmp_path, capsys):
        """Test CLI error handling when directories are not writable."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock fetch_and_extract to raise an error during directory validation
        from protonfetcher.exceptions import ProtonFetcherError

        mock_fetcher.fetch_and_extract.side_effect = ProtonFetcherError(
            "Directory not writable"
        )

        test_args = [
            "protonfetcher",
            "--extract-dir",
            str(tmp_path / "non_writable_dir"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # This should cause an error
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: Directory not writable" in captured.out

    def test_cli_missing_dependencies_error(self, mocker, tmp_path, capsys):
        """Test CLI error handling when required dependencies are missing."""
        # This test simulates a scenario where required system tools (like curl or tar) are not available
        # This would typically happen in the initialization of the managers

        # Mock a scenario where subprocess raises FileNotFoundError for missing tools
        mocker.patch("subprocess.run", side_effect=FileNotFoundError("curl not found"))

        test_args = [
            "protonfetcher",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # This should cause an error
        with pytest.raises(SystemExit) as exc_info:
            main()

        # The exact error code may vary depending on the implementation
        # But it should exit with an error
        assert exc_info.value.code == 1

    def test_cli_invalid_path_error(self, mocker, tmp_path, capsys):
        """Test CLI error handling with invalid paths."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock fetch_and_extract to raise an error during path validation
        from protonfetcher.exceptions import ProtonFetcherError

        mock_fetcher.fetch_and_extract.side_effect = ProtonFetcherError(
            "Path does not exist"
        )

        invalid_path = Path("/invalid/path/that/does/not/exist")
        test_args = [
            "protonfetcher",
            "--extract-dir",
            str(invalid_path),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # This should cause an error
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: Path does not exist" in captured.out

    def test_cli_rate_limit_error_handling(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI error handling for GitHub API rate limit errors."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock the list_recent_releases method to raise a rate limit error
        mock_fetcher.release_manager.list_recent_releases.side_effect = (
            ProtonFetcherError(
                "API rate limit exceeded. Please wait before trying again."
            )
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
            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: API rate limit exceeded" in captured.out

    def test_cli_asset_not_found_error(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI error handling when requested asset is not found."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock fetch_and_extract to raise an error when asset is not found
        from protonfetcher.exceptions import ProtonFetcherError

        mock_fetcher.fetch_and_extract.side_effect = ProtonFetcherError(
            "Asset not found"
        )

        test_args = [
            "protonfetcher",
            "-f",
            "GE-Proton",
            "-r",
            "GE-Proton99-99",  # Non-existent release
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Should exit with error code 1 due to asset not found
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error:" in captured.out
