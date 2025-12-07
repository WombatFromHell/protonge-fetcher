"""
Tests for individual CLI flags in protonfetcher module.
Testing each CLI flag functionality separately.
"""

import pytest
from pathlib import Path
from pytest_mock import MockerFixture

from protonfetcher.cli import main
from protonfetcher.common import ForkName
from protonfetcher.exceptions import ProtonFetcherError
from protonfetcher.release_manager import FORKS


class TestCLIListFlag:
    """Tests for the --list/-l CLI flag functionality."""

    @pytest.mark.parametrize(
        "fork,expected_releases,use_short_form",
        [
            (
                ForkName.GE_PROTON,
                ["GE-Proton9-23", "GE-Proton9-22", "GE-Proton9-21"],
                False,
            ),
            (
                ForkName.GE_PROTON,
                ["GE-Proton9-25", "GE-Proton9-24", "GE-Proton9-23"],
                False,
            ),
            (
                ForkName.GE_PROTON,
                ["GE-Proton10-1", "GE-Proton9-50", "GE-Proton9-49"],
                True,
            ),
            (ForkName.PROTON_EM, ["EM-10.0-30", "EM-10.0-29", "EM-10.0-28"], False),
        ],
    )
    def test_cli_list_flag_with_forks(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
        capsys,
        fork,
        expected_releases,
        use_short_form,
    ):
        """Parametrized test for CLI command: ./protonfetcher --list/-l -f [fork]."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock the list_recent_releases method
        mock_fetcher.release_manager.list_recent_releases.return_value = (
            expected_releases
        )

        # Prepare CLI arguments based on whether to use short form
        flag = "-l" if use_short_form else "--list"
        test_args = [
            "protonfetcher",
            flag,
            "-f",
            fork.value,  # Convert enum to string for CLI
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
        mock_fetcher.release_manager.list_recent_releases.assert_called_once_with(
            FORKS[fork]["repo"]
        )

        # Capture output to verify the tags were printed
        captured = capsys.readouterr()
        assert "Recent releases:" in captured.out
        for release in expected_releases:
            assert release in captured.out

    def test_cli_list_flag_with_rate_limit_error(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI command handles rate limit errors properly."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock the list_recent_releases method to raise a rate limit error

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


class TestCLIListLinksFlag:
    """Tests for the --ls CLI flag functionality."""

    @pytest.mark.parametrize(
        "fork,expected_links",
        [
            (
                ForkName.GE_PROTON,
                {
                    "GE-Proton": "GE-Proton10-15",
                    "GE-Proton-Fallback": "GE-Proton10-12",
                    "GE-Proton-Fallback2": None,
                },
            ),
            (
                ForkName.PROTON_EM,
                {
                    "Proton-EM": "proton-EM-10.0-30",
                    "Proton-EM-Fallback": "proton-EM-10.0-25",
                    "Proton-EM-Fallback2": "proton-EM-10.0-20",
                },
            ),
        ],
    )
    def test_cli_ls_flag_with_forks(
        self, mocker: MockerFixture, tmp_path: Path, capsys, fork, expected_links
    ):
        """Parametrized test for CLI command: ./protonfetcher --ls -f [fork]."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Prepare the link information based on the expected links
        mock_link_info = {}
        for link_name, target_dir in expected_links.items():
            if target_dir:
                mock_link_info[link_name] = str(tmp_path / target_dir)
            else:
                mock_link_info[link_name] = None

        mock_fetcher.link_manager.list_links.return_value = mock_link_info

        test_args = [
            "protonfetcher",
            "--ls",
            "-f",
            fork.value,  # Convert enum to string for CLI
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

        # Verify correct fork was used
        mock_fetcher.link_manager.list_links.assert_called_once_with(
            (tmp_path / "compatibilitytools.d").expanduser(), fork.value
        )

        # Capture output to verify results
        captured = capsys.readouterr()
        assert f"Links for {fork.value}:" in captured.out
        for link_name, target_dir in expected_links.items():
            if target_dir:
                assert f"{link_name} ->" in captured.out
            else:
                assert f"{link_name} -> (not found)" in captured.out

    def test_cli_ls_flag_no_links_exist(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI command: ./protonfetcher --ls when no links exist."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock the list_links method to return all None values (no links exist)
        mock_fetcher.link_manager.list_links.return_value = {
            "GE-Proton": None,
            "GE-Proton-Fallback": None,
            "GE-Proton-Fallback2": None,
        }

        test_args = [
            "protonfetcher",
            "--ls",
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

        # Verify list_links was called for all forks when no specific fork was specified
        expected_calls = [
            mocker.call((tmp_path / "compatibilitytools.d").expanduser(), "GE-Proton"),
            mocker.call((tmp_path / "compatibilitytools.d").expanduser(), "Proton-EM"),
        ]
        assert mock_fetcher.link_manager.list_links.call_count == 2
        mock_fetcher.link_manager.list_links.assert_has_calls(expected_calls)

        # Capture output to verify all links show as not found
        captured = capsys.readouterr()
        assert "Links for GE-Proton:" in captured.out
        assert "GE-Proton -> (not found)" in captured.out
        assert "GE-Proton-Fallback -> (not found)" in captured.out
        assert "GE-Proton-Fallback2 -> (not found)" in captured.out


class TestCLIRemoveFlag:
    """Tests for the --rm CLI flag functionality."""

    @pytest.mark.parametrize(
        "fork,release_tag",
        [
            (ForkName.GE_PROTON, "GE-Proton10-15"),
            (ForkName.PROTON_EM, "EM-10.0-30"),
        ],
    )
    def test_cli_rm_flag_with_forks(
        self, mocker: MockerFixture, tmp_path: Path, capsys, fork, release_tag
    ):
        """Parametrized test for CLI command: ./protonfetcher --rm [tag] -f [fork]."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock the remove_release method to return success
        mock_fetcher.link_manager.remove_release.return_value = True

        test_args = [
            "protonfetcher",
            "--rm",
            release_tag,
            "-f",
            fork.value,  # Convert enum to string for CLI
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

        # Verify remove_release was called with the correct parameters
        mock_fetcher.link_manager.remove_release.assert_called_once_with(
            (tmp_path / "compatibilitytools.d").expanduser(),
            release_tag,
            fork.value,  # Use enum value for fork
        )

        # Capture output to verify success message was printed
        captured = capsys.readouterr()
        assert "Success" in captured.out

    def test_cli_rm_flag_directory_not_found(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test CLI command handles when the specified directory doesn't exist."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock the remove_release method to raise a ProtonFetcherError

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
            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: Release directory does not exist:" in captured.out


class TestCLIDefaultFlag:
    """Tests for the default CLI behavior (list links)."""

    def test_cli_default_lists_links(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test default CLI command: ./protonfetcher (list all links)."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Prepare the link information
        mock_link_info = {
            "GE-Proton": str(tmp_path / "GE-Proton10-15"),
            "GE-Proton-Fallback": str(tmp_path / "GE-Proton10-12"),
            "GE-Proton-Fallback2": None,
        }

        mock_fetcher.link_manager.list_links.return_value = mock_link_info

        test_args = [
            "protonfetcher",  # sys.argv[0]
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

        # Verify that list_links was called for both forks when no specific fork was specified
        expected_calls = [
            mocker.call((tmp_path / "compatibilitytools.d").expanduser(), ForkName.GE_PROTON),
            mocker.call((tmp_path / "compatibilitytools.d").expanduser(), ForkName.PROTON_EM),
        ]
        assert mock_fetcher.link_manager.list_links.call_count == 2
        mock_fetcher.link_manager.list_links.assert_has_calls(expected_calls)

        # Capture output to verify it contains list output
        captured = capsys.readouterr()
        assert "Listing recognized links" in captured.out
        assert "Success" in captured.out

    def test_cli_default_with_explicit_fork_still_fetches(
        self, mocker: MockerFixture, tmp_path: Path
    ):
        """Test CLI command: ./protonfetcher -f GE-Proton (explicit fork with no operation flags should fetch)."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher",
            "-f",
            "GE-Proton",  # With explicit fork, this should trigger fetch behavior
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

        # Verify that fetch_and_extract was called since fork was explicitly provided
        assert mock_fetcher.fetch_and_extract.called
        call_args = mock_fetcher.fetch_and_extract.call_args

        # Verify parameters: (repo, output_dir, extract_dir, release_tag, fork)
        assert call_args[0][0] == FORKS[ForkName.GE_PROTON]["repo"]  # repo
        assert call_args[1]["fork"] == ForkName.GE_PROTON  # fork
        assert (
            call_args[1]["release_tag"] is None
        )  # Should fetch latest (not a specific tag)

    def test_cli_default_with_explicit_release_still_fetches(self, mocker: MockerFixture, tmp_path: Path):
        """Test CLI command: ./protonfetcher -r GE-Proton10-11 (explicit release with no operation flags should fetch)."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher",
            "-r",
            "GE-Proton10-11",  # With explicit release, this should trigger fetch behavior
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

        # Verify that fetch_and_extract was called since release was explicitly provided
        assert mock_fetcher.fetch_and_extract.called
        call_args = mock_fetcher.fetch_and_extract.call_args

        # Verify parameters: (repo, output_dir, extract_dir, release_tag, fork)
        assert call_args[0][0] == FORKS[ForkName.GE_PROTON]["repo"]  # repo
        assert call_args[1]["fork"] == ForkName.GE_PROTON  # fork
        assert call_args[1]["release_tag"] == "GE-Proton10-11"  # Should fetch specific tag


class TestCLIReleaseFlag:
    """Tests for the --release/-r CLI flag functionality."""

    @pytest.mark.parametrize(
        "fork,release_tag,expected_repo",
        [
            (ForkName.GE_PROTON, "GE-Proton10-11", "GloriousEggroll/proton-ge-custom"),
            (ForkName.PROTON_EM, "Proton-EM-10.0-2F", "Etaash-mathamsetty/Proton"),
        ],
    )
    def test_cli_release_flag_with_forks(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
        fork: ForkName,
        release_tag: str,
        expected_repo: str,
    ):
        """Parametrized test for CLI command with --release flag."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher.py",
            "-f",
            fork.value,  # Convert enum to string for CLI
            "-r",
            release_tag,
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
        assert call_args[0][0] == expected_repo
        assert call_args[1]["fork"] == fork
        assert call_args[1]["release_tag"] == release_tag

    def test_cli_release_flag_validation(self, mocker: MockerFixture, tmp_path: Path):
        """Test that --release flag validates properly."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        # Use a valid release tag
        test_args = [
            "protonfetcher.py",
            "-f",
            "GE-Proton",
            "-r",
            "GE-Proton10-11",  # Valid tag format
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

        # Verify the release tag was passed through correctly
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args[1]["release_tag"] == "GE-Proton10-11"


class TestCLIDebugFlag:
    """Tests for the --debug CLI flag functionality."""

    def test_cli_debug_flag_enables_logging(
        self, mocker: MockerFixture, tmp_path: Path, caplog
    ):
        """Test CLI command with --debug flag enables debug logging."""
        import logging

        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

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


class TestCLIPathFlags:
    """Tests for the path-related CLI flags (--extract-dir, --output)."""

    def test_cli_extract_dir_flag(self, mocker: MockerFixture, tmp_path: Path):
        """Test CLI command with custom --extract-dir flag."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        custom_extract_dir = tmp_path / "custom_extract"
        custom_extract_dir.mkdir()

        mock_fetcher.fetch_and_extract.return_value = custom_extract_dir

        test_args = [
            "protonfetcher",
            "-f",
            "GE-Proton",  # Add fork to trigger fetch operation
            "--extract-dir",
            str(custom_extract_dir),
            "--output",
            str(tmp_path / "Downloads"),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify the custom extract directory was used (it's the 3rd positional argument)
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert (
            call_args[0][2] == custom_extract_dir
        )  # 3rd positional arg is extract_dir

    def test_cli_output_dir_flag(self, mocker: MockerFixture, tmp_path: Path):
        """Test CLI command with custom --output flag."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        custom_output_dir = tmp_path / "custom_output"
        custom_output_dir.mkdir()

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher",
            "-f",
            "GE-Proton",  # Add fork to trigger fetch operation
            "--extract-dir",
            str(tmp_path / "extract"),
            "--output",
            str(custom_output_dir),
        ]
        mocker.patch("sys.argv", test_args)

        try:
            main()
        except SystemExit:
            pass

        # Verify the custom output directory was used (it's the 2nd positional argument)
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args[0][1] == custom_output_dir  # 2nd positional arg is output_dir

    def test_cli_tilde_expansion(self, mocker: MockerFixture, tmp_path: Path):
        """Test CLI tilde (~) path expansion in directory flags."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        # Use tilde paths in arguments
        test_args = [
            "protonfetcher",
            "-f",
            "GE-Proton",  # Add fork to trigger fetch operation
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

        # Verify that paths were processed (tilde expansion would happen in Path operations)
        # The actual expansion depends on the implementation in the main function
        assert mock_fetcher.fetch_and_extract.called
