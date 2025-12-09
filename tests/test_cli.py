"""
CLI tests for protonfetcher module.
Testing the actual user-facing commands and their expected behavior.
"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protonfetcher.cli import main
from protonfetcher.common import ForkName
from protonfetcher.exceptions import ProtonFetcherError
from protonfetcher.release_manager import FORKS

# For backward compatibility in tests
ProtonFetcherError = ProtonFetcherError


class TestCLIForkScenarios:
    """Parametrized tests for CLI operations with different Proton forks."""

    @pytest.mark.parametrize(
        "fork,expected_repo",
        [
            (ForkName.GE_PROTON, "GloriousEggroll/proton-ge-custom"),
            (ForkName.PROTON_EM, "Etaash-mathamsetty/Proton"),
        ],
    )
    def test_cli_get_latest_all_forks(
        self, mocker: MockerFixture, tmp_path: Path, fork: ForkName, expected_repo: str
    ):
        """Parametrized test for CLI command for getting latest release for any fork."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher",
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

        # Verify correct repo and fork were used
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args[0][0] == expected_repo
        assert call_args[1]["fork"] == fork
        assert call_args[1]["release_tag"] is None  # Should fetch latest

    @pytest.mark.parametrize(
        "fork,manual_tag,expected_repo",
        [
            (ForkName.GE_PROTON, "GE-Proton10-11", "GloriousEggroll/proton-ge-custom"),
            (ForkName.PROTON_EM, "Proton-EM-10.0-2F", "Etaash-mathamsetty/Proton"),
        ],
    )
    def test_cli_get_manual_all_forks(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
        fork: ForkName,
        manual_tag: str,
        expected_repo: str,
    ):
        """Parametrized test for CLI command for getting manual release for any fork."""
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
            manual_tag,
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

        # Verify correct repo, fork, and tag were used
        call_args = mock_fetcher.fetch_and_extract.call_args
        assert call_args[0][0] == expected_repo
        assert call_args[1]["fork"] == fork
        assert call_args[1]["release_tag"] == manual_tag

    @pytest.mark.parametrize(
        "fork,release_tag,expected_repo",
        [
            (ForkName.GE_PROTON, None, "GloriousEggroll/proton-ge-custom"),
            (ForkName.PROTON_EM, None, "Etaash-mathamsetty/Proton"),
            (ForkName.GE_PROTON, "GE-Proton10-11", "GloriousEggroll/proton-ge-custom"),
            (ForkName.PROTON_EM, "Proton-EM-10.0-2F", "Etaash-mathamsetty/Proton"),
        ],
    )
    def test_cli_all_fork_release_combinations(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
        fork: ForkName,
        release_tag: str,
        expected_repo: str,
    ):
        """Test all combinations of forks and release tags."""
        mock_fetcher = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        mock_fetcher.fetch_and_extract.return_value = tmp_path / "extract"

        test_args = [
            "protonfetcher",
            "-f",
            fork.value,
        ]  # Convert enum to string for CLI
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
        assert call_args[1]["fork"] == fork  # fork is now the enum type
        if release_tag:
            assert call_args[1]["release_tag"] == release_tag
        else:
            assert call_args[1]["release_tag"] is None


class TestCLIListReleases:
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


class TestCLIListAndRemove:
    """Tests for the new --ls and --rm CLI flags functionality."""

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
            main()

        assert exc_info.value.code == 1

        # Capture output to verify error message
        captured = capsys.readouterr()
        assert "Error: Release directory does not exist:" in captured.out

    def test_cli_ls_rm_mixed_with_other_flags_error(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test that --ls and --rm cannot be used with other conflicting flags."""
        # Test --ls with --list
        test_args = [
            "protonfetcher",
            "--ls",
            "--list",
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
        assert "Error: --ls cannot be used with --release or --list" in captured.out

    def test_cli_rm_mixed_with_other_flags_error(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test that --rm cannot be used with other conflicting flags."""
        # Test --rm with --list
        test_args = [
            "protonfetcher",
            "--rm",
            "GE-Proton10-15",
            "--list",
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
        assert (
            "Error: --rm cannot be used with --release, --list, or --ls" in captured.out
        )

    def test_cli_ls_rm_with_release_flag_error(
        self, mocker: MockerFixture, tmp_path: Path, capsys
    ):
        """Test that --ls and --rm cannot be used with --release flag."""
        # Test --ls with --release
        test_args = [
            "protonfetcher",
            "--ls",
            "--release",
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
        assert "Error: --ls cannot be used with --release or --list" in captured.out


class TestCLIArgumentValidation:
    """Tests for CLI argument validation and error handling."""

    @pytest.mark.parametrize(
        "invalid_fork_name",
        [
            "InvalidForkName",
            "nonexistent",
            "wrong-name",
            "123invalid",
            "",
        ],
    )
    def test_cli_invalid_fork_string_conversion(
        self, mocker, tmp_path, capsys, invalid_fork_name
    ):
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
            invalid_fork_name,  # Invalid fork name
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
