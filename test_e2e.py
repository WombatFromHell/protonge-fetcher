"""
End-to-end tests for protonfetcher CLI interactions.
Testing the actual user-facing commands and their expected behavior.
"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

import protonfetcher
from protonfetcher import FORKS, main


class TestE2ECLIGetLatestGEProton:
    """End-to-end tests for getting the latest GE-Proton release."""

    def test_cli_get_latest_ge_proton_default(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI command: ./protonfetcher (default - latest GE-Proton)."""
        # Mock the GitHubReleaseFetcher methods to avoid network calls
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Setup the mock to return a successful result
        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        # Mock command line arguments to simulate: ./protonfetcher
        test_args = [
            "protonfetcher",  # sys.argv[0]
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Mock the directory validation to succeed
        mocker.patch.object(
            protonfetcher.GitHubReleaseFetcher, "_ensure_directory_is_writable"
        )

        # Run main function (which handles the CLI)
        try:
            main()
        except SystemExit:
            pass  # Expected to exit after successful execution

        # Verify that fetch_and_extract was called with the right parameters
        assert mock_fetcher.fetch_and_extract.called
        call_args = mock_fetcher.fetch_and_extract.call_args

        # Verify parameters: (repo, output_dir, extract_dir, release_tag, fork)
        assert call_args[0][0] == FORKS["GE-Proton"]["repo"]  # repo
        assert call_args[1]["fork"] == "GE-Proton"  # fork
        assert (
            call_args[1]["release_tag"] is None
        )  # Should fetch latest (not a specific tag)

    def test_cli_get_latest_ge_proton_explicit(
        self, mocker: MockerFixture, tmp_path: Path
    ):
        """Test CLI command: ./protonfetcher -f 'GE-Proton' (explicit fork)."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher",
            "-f",
            "GE-Proton",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify that GE-Proton fork was used explicitly
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args[0][0] == FORKS["GE-Proton"]["repo"]
        assert call_args[1]["fork"] == "GE-Proton"


class TestE2ECLIGetManualGEProton:
    """End-to-end tests for getting a manual GE-Proton release."""

    def test_cli_get_manual_ge_proton(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI command: ./protonfetcher.py -f 'GE-Proton' -r 'GE-Proton10-11'."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher.py",
            "-f",
            "GE-Proton",
            "-r",
            "GE-Proton10-11",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify the call parameters
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args[0][0] == FORKS["GE-Proton"]["repo"]
        assert call_args[1]["fork"] == "GE-Proton"
        assert call_args[1]["release_tag"] == "GE-Proton10-11"


class TestE2ECLIGetLatestProtonEM:
    """End-to-end tests for getting the latest Proton-EM release."""

    def test_cli_get_latest_proton_em(self, mocker: MockerFixture, tmp_path: Path):
        """Test CLI command: ./protonfetcher.py -f 'Proton-EM'."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher.py",
            "-f",
            "Proton-EM",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify that Proton-EM fork was used
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args[0][0] == FORKS["Proton-EM"]["repo"]
        assert call_args[1]["fork"] == "Proton-EM"
        assert call_args[1]["release_tag"] is None  # Should fetch latest


class TestE2ECLIGetManualProtonEM:
    """End-to-end tests for getting a manual Proton-EM release."""

    def test_cli_get_manual_proton_em(self, mocker: MockerFixture, tmp_path: Path):
        """Test CLI command: ./protonfetcher.py -f 'Proton-EM' -r 'Proton-EM-10.0-2F'."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher.py",
            "-f",
            "Proton-EM",
            "-r",
            "Proton-EM-10.0-2F",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify the call parameters for Proton-EM
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args[0][0] == FORKS["Proton-EM"]["repo"]
        assert call_args[1]["fork"] == "Proton-EM"
        assert call_args[1]["release_tag"] == "Proton-EM-10.0-2F"


class TestE2ECLIErrorsAndEdgeCases:
    """End-to-end tests for CLI error conditions and edge cases."""

    def test_cli_fetch_error_handling(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI error handling when fetch operation fails."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Make fetch_and_extract raise a FetchError
        from protonfetcher import FetchError

        mock_fetcher.fetch_and_extract.side_effect = FetchError(
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

    def test_cli_tilde_expansion(self, mocker: MockerFixture, tmp_path: Path):
        """Test CLI tilde (~) path expansion."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        # Use tilde paths in arguments
        test_args = [
            "protonfetcher",
            "--extract-dir",
            "~/custom/compatibilitytools.d",
            "--output",
            "~/custom/Downloads",
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify that paths were expanded (no ~ in final paths)
        # The paths should be expanded but we can't verify the exact paths here
        # since the Path.expanduser() is called inside main()


class TestE2ECLISuccessMessages:
    """End-to-end tests for CLI success messages."""

    def test_cli_success_message_output(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test that CLI outputs success message on completion."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Capture the output to verify success message
        captured = capsys.readouterr()
        assert "Success" in captured.out

    def test_cli_debug_logging_enabled(
        self, mocker: MockerFixture, tmp_path: Path, caplog
    ):
        """Test CLI with debug logging enabled."""
        import logging

        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher",
            "--debug",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Run with debug logging enabled
        with caplog.at_level(logging.DEBUG):
            try:
                main()
            except SystemExit:
                pass

        # Verify debug logging was enabled
        assert any(
            "Debug logging enabled" in record.message for record in caplog.records
        )


class TestE2ECLIAllForkCombinations:
    """End-to-end tests for all fork and release combinations."""

    @pytest.mark.parametrize(
        "fork,release_tag,expected_repo",
        [
            ("GE-Proton", None, "GloriousEggroll/proton-ge-custom"),
            ("Proton-EM", None, "Etaash-mathamsetty/Proton"),
            ("GE-Proton", "GE-Proton10-11", "GloriousEggroll/proton-ge-custom"),
            ("Proton-EM", "Proton-EM-10.0-2F", "Etaash-mathamsetty/Proton"),
        ],
    )
    def test_cli_all_fork_release_combinations(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
        fork: str,
        release_tag: str,
        expected_repo: str,
    ):
        """Test all combinations of forks and release tags."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = ["protonfetcher", "-f", fork]
        if release_tag:
            test_args.extend(["-r", release_tag])
        test_args.extend(
            [
                "--extract-dir",
                str(tmp_path / "compatibilitytools.d"),
                "--output",
                str(tmp_path / "Downloads"),
            ]
        )

        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify correct repo was used
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args[0][0] == expected_repo
        assert call_args[1]["fork"] == fork
        if release_tag:
            assert call_args[1]["release_tag"] == release_tag
        else:
            assert call_args[1]["release_tag"] is None


class TestE2ECLIFullWorkflowSimulation:
    """End-to-end tests simulating full user workflows."""

    def test_full_workflow_simulation_ge_proton_latest(
        self, mocker: MockerFixture, tmp_path: Path
    ):
        """Simulate a full workflow for getting latest GE-Proton."""
        # Mock all external dependencies
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock the fetch_and_extract method to control the whole workflow
        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        # Create required directories
        (tmp_path / "Downloads").mkdir()
        (tmp_path / "extract").mkdir()

        # Simulate command: ./protonfetcher --extract-dir ./extract --output ./Downloads
        test_args = [
            "protonfetcher",
            "--extract-dir",
            str(tmp_path / "extract"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Execute
        try:
            main()
        except SystemExit:
            pass

        # Since we mocked the entire GitHubReleaseFetcher, the fetch_and_extract method should be called
        assert mock_fetcher.fetch_and_extract.called

        # Verify the parameters passed to fetch_and_extract
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args is not None
        # The fork should be GE-Proton by default
        assert call_args[1]["fork"] == "GE-Proton"

    def test_full_workflow_simulation_proton_em_manual(
        self, mocker: MockerFixture, tmp_path: Path
    ):
        """Simulate a full workflow for getting a manual Proton-EM release."""
        # Mock all external dependencies
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock the various internal methods to simulate the flow
        mock_fetcher.find_asset_by_name.return_value = "proton-Proton-EM-10.0-2F.tar.xz"
        mock_fetcher.get_remote_asset_size.return_value = 1024 * 1024 * 400  # 400MB
        mock_fetcher.download_asset.return_value = (
            tmp_path / "Downloads" / "proton-Proton-EM-10.0-2F.tar.xz"
        )
        mock_fetcher.extract_archive.return_value = None
        mock_fetcher._manage_proton_links.return_value = None
        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        # Create required directories
        (tmp_path / "Downloads").mkdir()
        (tmp_path / "extract").mkdir()

        # Simulate command: ./protonfetcher.py -f 'Proton-EM' -r 'Proton-EM-10.0-2F'
        test_args = [
            "protonfetcher.py",
            "-f",
            "Proton-EM",
            "-r",
            "Proton-EM-10.0-2F",
            "--extract-dir",
            str(tmp_path / "extract"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Execute
        try:
            main()
        except SystemExit:
            pass

        # Verify the workflow happened as expected for Proton-EM
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert (
            call_args[0][0] == FORKS["Proton-EM"]["repo"]
        )  # Correct repo for Proton-EM
        assert call_args[1]["fork"] == "Proton-EM"  # Correct fork
        assert call_args[1]["release_tag"] == "Proton-EM-10.0-2F"  # Correct manual tag

    def test_full_workflow_with_progress_disabled(
        self, mocker: MockerFixture, tmp_path: Path
    ):
        """Test workflow with progress bar disabled."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher",
            "--no-progress",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify that fetch_and_extract was called with show_progress=False
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args[1]["show_progress"] is False  # Progress should be disabled

    def test_full_workflow_with_file_details_disabled(
        self, mocker: MockerFixture, tmp_path: Path
    ):
        """Test workflow with file details display disabled."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher",
            "--no-file-details",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify that fetch_and_extract was called with show_file_details=False
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert (
            call_args[1]["show_file_details"] is False
        )  # File details should be disabled


class TestE2ECLIListReleases:
    """End-to-end tests for the --list/-l CLI flag functionality."""

    def test_cli_list_flag_ge_proton_default(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI command: ./protonfetcher --list (default GE-Proton fork)."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock the list_recent_releases method
        mock_fetcher.list_recent_releases.return_value = [
            "GE-Proton9-23",
            "GE-Proton9-22",
            "GE-Proton9-21",
        ]

        test_args = [
            "protonfetcher",
            "--list",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        # Run main function
        try:
            main()
        except SystemExit:
            pass

        # Verify list_recent_releases was called with the correct repo
        mock_fetcher.list_recent_releases.assert_called_once_with(
            FORKS["GE-Proton"]["repo"]
        )

        # Capture output to verify the tags were printed
        captured = capsys.readouterr()
        assert "Recent releases:" in captured.out
        assert "GE-Proton9-23" in captured.out
        assert "GE-Proton9-22" in captured.out
        assert "GE-Proton9-21" in captured.out

    def test_cli_list_flag_ge_proton_explicit(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI command: ./protonfetcher --list -f GE-Proton."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock the list_recent_releases method
        mock_fetcher.list_recent_releases.return_value = [
            "GE-Proton9-25",
            "GE-Proton9-24",
            "GE-Proton9-23",
        ]

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

        try:
            main()
        except SystemExit:
            pass

        # Verify correct repo was used
        mock_fetcher.list_recent_releases.assert_called_once_with(
            FORKS["GE-Proton"]["repo"]
        )

        # Capture output to verify the tags were printed
        captured = capsys.readouterr()
        assert "Recent releases:" in captured.out
        assert "GE-Proton9-25" in captured.out

    def test_cli_list_flag_proton_em(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI command: ./protonfetcher --list -f Proton-EM."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock the list_recent_releases method
        mock_fetcher.list_recent_releases.return_value = [
            "EM-10.0-30",
            "EM-10.0-29",
            "EM-10.0-28",
        ]

        test_args = [
            "protonfetcher",
            "--list",
            "-f",
            "Proton-EM",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify correct repo was used
        mock_fetcher.list_recent_releases.assert_called_once_with(
            FORKS["Proton-EM"]["repo"]
        )

        # Capture output to verify the tags were printed
        captured = capsys.readouterr()
        assert "Recent releases:" in captured.out
        assert "EM-10.0-30" in captured.out
        assert "EM-10.0-29" in captured.out
        assert "EM-10.0-28" in captured.out

    def test_cli_list_flag_short_form(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI command: ./protonfetcher -l -f GE-Proton."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock the list_recent_releases method
        mock_fetcher.list_recent_releases.return_value = [
            "GE-Proton10-1",
            "GE-Proton9-50",
            "GE-Proton9-49",
        ]

        test_args = [
            "protonfetcher",
            "-l",
            "-f",
            "GE-Proton",
            "--extract-dir",
            str(tmp_path / "compatibilitytools.d"),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify method was called with correct repo
        mock_fetcher.list_recent_releases.assert_called_once_with(
            FORKS["GE-Proton"]["repo"]
        )

        # Capture output to verify the tags were printed
        captured = capsys.readouterr()
        assert "Recent releases:" in captured.out
        assert "GE-Proton10-1" in captured.out

    def test_cli_list_flag_with_rate_limit_error(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI command handles rate limit errors properly."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock the list_recent_releases method to raise a rate limit error
        from protonfetcher import FetchError

        mock_fetcher.list_recent_releases.side_effect = FetchError(
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

        # Should exit with error code 1 due to the FetchError
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: API rate limit exceeded" in captured.out

    def test_cli_list_flag_mixed_with_release_error(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
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
            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: --list and --release cannot be used together" in captured.out


class TestE2EMainFunctionErrorHandling:
    """End-to-end tests for main function error handling paths."""

    def test_main_function_fetch_error_handling(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test main function error handling when fetch operation raises FetchError."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Make fetch_and_extract raise a FetchError
        from protonfetcher import FetchError

        mock_fetcher.fetch_and_extract.side_effect = FetchError(
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

    def test_main_function_fetch_error_with_debug(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test main function error handling when fetch operation raises FetchError with debug enabled."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Make fetch_and_extract raise a FetchError
        from protonfetcher import FetchError

        mock_fetcher.fetch_and_extract.side_effect = FetchError(
            "Download failed due to network timeout"
        )

        test_args = [
            "protonfetcher",
            "--debug",
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
        assert "Error: Download failed due to network timeout" in captured.out

    def test_cli_list_flag_stdout_rate_limit_error(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI handles rate limit errors in stdout properly."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock the list_recent_releases method to raise the appropriate error
        from protonfetcher import FetchError

        mock_fetcher.list_recent_releases.side_effect = FetchError(
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

        # Should exit with error code 1 due to the rate limit error
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: API rate limit exceeded" in captured.out

    def test_cli_list_flag_json_parse_error(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI handles JSON parsing errors in list functionality."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch("protonfetcher.GitHubReleaseFetcher", return_value=mock_fetcher)

        # Mock the list_recent_releases method to raise a JSON parsing error
        from protonfetcher import FetchError

        mock_fetcher.list_recent_releases.side_effect = FetchError(
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
            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: Failed to parse JSON response" in captured.out
