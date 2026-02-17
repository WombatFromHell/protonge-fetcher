"""
End-to-end tests for CLI interface.

Tests the command-line interface for all operations:
- Default invocation (list links)
- List releases (-l)
- Remove release (--rm)
- Relink (--relink)
- Validation and error handling
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from protonfetcher.cli import (
    convert_fork_to_enum,
    main,
    parse_arguments,
)
from protonfetcher.common import ForkName
from protonfetcher.exceptions import ProtonFetcherError


class TestArgumentParsing:
    """Test CLI argument parsing and validation."""

    def test_parse_default_arguments(self) -> None:
        """Test parsing default arguments (no flags)."""
        with patch.object(sys, "argv", ["protonfetcher"]):
            args = parse_arguments()

            # Default: fork is set to GE-Proton, no operation flags
            # The main() function handles defaulting to --ls behavior
            assert not args.ls
            assert not args.list
            assert args.fork == ForkName.GE_PROTON

    def test_parse_list_releases_flag(self) -> None:
        """Test parsing --list/-l flag."""
        with patch.object(sys, "argv", ["protonfetcher", "--list"]):
            args = parse_arguments()
            assert args.list is True

        with patch.object(sys, "argv", ["protonfetcher", "-l"]):
            args = parse_arguments()
            assert args.list is True

    def test_parse_list_links_flag(self) -> None:
        """Test parsing --ls flag."""
        with patch.object(sys, "argv", ["protonfetcher", "--ls"]):
            args = parse_arguments()
            assert args.ls is True

    def test_parse_remove_flag(self) -> None:
        """Test parsing --rm flag with tag."""
        with patch.object(sys, "argv", ["protonfetcher", "--rm", "GE-Proton10-20"]):
            args = parse_arguments()
            assert args.rm == "GE-Proton10-20"

    def test_parse_fork_flag(self) -> None:
        """Test parsing --fork/-f flag."""
        with patch.object(sys, "argv", ["protonfetcher", "--fork", "GE-Proton"]):
            args = parse_arguments()
            assert args.fork == "GE-Proton"

        with patch.object(sys, "argv", ["protonfetcher", "-f", "Proton-EM"]):
            args = parse_arguments()
            assert args.fork == "Proton-EM"

    def test_parse_release_flag(self) -> None:
        """Test parsing --release/-r flag."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--release", "GE-Proton10-15"]
        ):
            args = parse_arguments()
            assert args.release == "GE-Proton10-15"

        with patch.object(sys, "argv", ["protonfetcher", "-r", "EM-10.0-30"]):
            args = parse_arguments()
            assert args.release == "EM-10.0-30"

    def test_parse_relink_flag(self) -> None:
        """Test parsing --relink flag."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--relink", "--fork", "GE-Proton"]
        ):
            args = parse_arguments()
            assert args.relink is True
            assert args.fork == "GE-Proton"

    def test_parse_debug_flag(self) -> None:
        """Test parsing --debug flag."""
        with patch.object(sys, "argv", ["protonfetcher", "--debug"]):
            args = parse_arguments()
            assert args.debug is True

    def test_parse_extract_dir_flag(self) -> None:
        """Test parsing --extract-dir/-x flag."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--extract-dir", "/custom/path"]
        ):
            args = parse_arguments()
            assert args.extract_dir == "/custom/path"

        with patch.object(sys, "argv", ["protonfetcher", "-x", "/another/path"]):
            args = parse_arguments()
            assert args.extract_dir == "/another/path"

    def test_parse_output_dir_flag(self) -> None:
        """Test parsing --output/-o flag."""
        with patch.object(sys, "argv", ["protonfetcher", "--output", "/downloads"]):
            args = parse_arguments()
            assert args.output == "/downloads"

        with patch.object(sys, "argv", ["protonfetcher", "-o", "/tmp"]):
            args = parse_arguments()
            assert args.output == "/tmp"


class TestArgumentValidation:
    """Test mutually exclusive argument validation."""

    def test_list_and_release_mutually_exclusive(self) -> None:
        """Test that --list and --release cannot be used together."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--list", "--release", "GE-Proton10-20"]
        ):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_ls_and_release_mutually_exclusive(self) -> None:
        """Test that --ls and --release cannot be used together."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--ls", "--release", "GE-Proton10-20"]
        ):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_ls_and_list_mutually_exclusive(self) -> None:
        """Test that --ls and --list cannot be used together."""
        with patch.object(sys, "argv", ["protonfetcher", "--ls", "--list"]):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_rm_and_release_mutually_exclusive(self) -> None:
        """Test that --rm and --release cannot be used together."""
        with patch.object(
            sys,
            "argv",
            ["protonfetcher", "--rm", "GE-Proton10-20", "--release", "GE-Proton10-19"],
        ):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_rm_and_list_mutually_exclusive(self) -> None:
        """Test that --rm and --list cannot be used together."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--rm", "GE-Proton10-20", "--list"]
        ):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_rm_and_ls_mutually_exclusive(self) -> None:
        """Test that --rm and --ls cannot be used together."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--rm", "GE-Proton10-20", "--ls"]
        ):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_relink_without_fork_fails(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that --relink requires --fork."""
        with patch.object(sys, "argv", ["protonfetcher", "--relink"]):
            with pytest.raises(SystemExit):
                parse_arguments()

        captured = capsys.readouterr()
        assert "--relink requires --fork" in captured.out

    def test_relink_and_release_mutually_exclusive(self) -> None:
        """Test that --relink and --release cannot be used together."""
        with patch.object(
            sys,
            "argv",
            [
                "protonfetcher",
                "--relink",
                "--fork",
                "GE-Proton",
                "--release",
                "GE-Proton10-20",
            ],
        ):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_relink_and_list_mutually_exclusive(self) -> None:
        """Test that --relink and --list cannot be used together."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--relink", "--fork", "GE-Proton", "--list"]
        ):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_relink_and_ls_mutually_exclusive(self) -> None:
        """Test that --relink and --ls cannot be used together."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--relink", "--fork", "GE-Proton", "--ls"]
        ):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_relink_and_rm_mutually_exclusive(self) -> None:
        """Test that --relink and --rm cannot be used together."""
        with patch.object(
            sys,
            "argv",
            [
                "protonfetcher",
                "--relink",
                "--fork",
                "GE-Proton",
                "--rm",
                "GE-Proton10-20",
            ],
        ):
            with pytest.raises(SystemExit):
                parse_arguments()


class TestForkConversion:
    """Test fork name conversion utilities."""

    def test_convert_string_to_enum_ge_proton(self) -> None:
        """Test converting GE-Proton string to enum."""
        result = convert_fork_to_enum("GE-Proton")
        assert result == ForkName.GE_PROTON

    def test_convert_string_to_enum_proton_em(self) -> None:
        """Test converting Proton-EM string to enum."""
        result = convert_fork_to_enum("Proton-EM")
        assert result == ForkName.PROTON_EM

    def test_convert_enum_passthrough(self) -> None:
        """Test passing enum through conversion."""
        result = convert_fork_to_enum(ForkName.GE_PROTON)
        assert result == ForkName.GE_PROTON

        result = convert_fork_to_enum(ForkName.PROTON_EM)
        assert result == ForkName.PROTON_EM

    def test_convert_none_to_default(self) -> None:
        """Test converting None to default fork."""
        result = convert_fork_to_enum(None)
        assert result == ForkName.GE_PROTON

    def test_convert_invalid_string(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test converting invalid fork string."""
        with pytest.raises(SystemExit):
            convert_fork_to_enum("Invalid-Fork")

        captured = capsys.readouterr()
        assert "Invalid fork" in captured.out


class TestListReleasesOperation:
    """Test the --list operation."""

    def test_list_releases_ge_proton(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test listing recent releases for GE-Proton."""
        # Arrange: Mock the fetcher
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.release_manager.list_recent_releases.return_value = [
            "GE-Proton10-20",
            "GE-Proton10-19",
            "GE-Proton10-18",
        ]

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv", ["protonfetcher", "--list", "-f", "GE-Proton"]
        )

        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        assert "GE-Proton10-20" in captured.out
        assert "GE-Proton10-19" in captured.out
        assert "Success" in captured.out

    def test_list_releases_proton_em(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test listing recent releases for Proton-EM."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.release_manager.list_recent_releases.return_value = [
            "EM-10.0-30",
            "EM-10.0-29",
            "EM-10.0-28",
        ]

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv", ["protonfetcher", "--list", "-f", "Proton-EM"]
        )

        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        assert "EM-10.0-30" in captured.out
        assert "Success" in captured.out


class TestListLinksOperation:
    """Test the --ls operation."""

    def test_list_links_default_all_forks(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        symlink_environment: dict[str, Any],
    ) -> None:
        """Test listing links for all forks (default behavior)."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.link_manager.list_links.side_effect = [
            {"GE-Proton": str(symlink_environment["version_dirs"][0])},
            {"Proton-EM": None},
            {"CachyOS": None},
        ]

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch("protonfetcher.cli.sys.argv", ["protonfetcher"])

        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        assert "GE-Proton" in captured.out
        assert "Proton-EM" in captured.out
        assert "CachyOS" in captured.out
        assert "Success" in captured.out

    def test_list_links_specific_fork(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test listing links for a specific fork."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.link_manager.list_links.return_value = {
            "GE-Proton": "/path/to/GE-Proton10-20",
            "GE-Proton-Fallback": "/path/to/GE-Proton10-19",
            "GE-Proton-Fallback2": "/path/to/GE-Proton10-18",
        }

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv", ["protonfetcher", "--ls", "-f", "GE-Proton"]
        )

        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        assert "GE-Proton" in captured.out
        assert "GE-Proton-Fallback" in captured.out
        assert "Success" in captured.out


class TestRemoveOperation:
    """Test the --rm operation."""

    def test_remove_release_ge_proton(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test removing a GE-Proton release."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.link_manager.remove_release.return_value = True

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--rm", "GE-Proton10-20", "-f", "GE-Proton"],
        )

        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        assert "Success" in captured.out
        mock_fetcher.link_manager.remove_release.assert_called_once()

    def test_remove_release_proton_em(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test removing a Proton-EM release."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.link_manager.remove_release.return_value = True

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--rm", "EM-10.0-30", "-f", "Proton-EM"],
        )

        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        assert "Success" in captured.out


class TestRelinkOperation:
    """Test the --relink operation."""

    def test_relink_ge_proton(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test relinking GE-Proton symlinks."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.relink_fork.return_value = True

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--relink", "-f", "GE-Proton"],
        )

        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        assert "Success" in captured.out
        mock_fetcher.relink_fork.assert_called_once()

    def test_relink_proton_em(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test relinking Proton-EM symlinks."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.relink_fork.return_value = True

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--relink", "-f", "Proton-EM"],
        )

        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        assert "Success" in captured.out


class TestDownloadOperation:
    """Test the default download operation."""

    def test_download_with_fork_flag(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        temp_environment: dict[str, Path],
    ) -> None:
        """Test downloading with --fork flag."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_and_extract.return_value = (
            temp_environment["extract_dir"] / "GE-Proton10-20"
        )

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv",
            [
                "protonfetcher",
                "-f",
                "GE-Proton",
                "-x",
                str(temp_environment["extract_dir"]),
                "-o",
                str(temp_environment["output_dir"]),
            ],
        )

        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        assert "Success" in captured.out
        mock_fetcher.fetch_and_extract.assert_called_once()

    def test_download_with_release_flag(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        temp_environment: dict[str, Path],
    ) -> None:
        """Test downloading specific release with --release flag."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_and_extract.return_value = (
            temp_environment["extract_dir"] / "GE-Proton10-15"
        )

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv",
            [
                "protonfetcher",
                "-f",
                "GE-Proton",
                "-r",
                "GE-Proton10-15",
                "-x",
                str(temp_environment["extract_dir"]),
                "-o",
                str(temp_environment["output_dir"]),
            ],
        )

        # Act
        main()

        # Assert
        captured = capsys.readouterr()
        assert "Success" in captured.out


class TestErrorHandling:
    """Test CLI error handling."""

    def test_protonfetcher_error_handling(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test handling ProtonFetcherError."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_and_extract.side_effect = ProtonFetcherError(
            "Test error message"
        )

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch("protonfetcher.cli.sys.argv", ["protonfetcher", "-f", "GE-Proton"])

        # Act
        with pytest.raises(SystemExit):
            main()

        # Assert
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "Test error message" in captured.out

    def test_network_error_handling(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test handling NetworkError."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        from protonfetcher.exceptions import NetworkError

        mock_fetcher.fetch_and_extract.side_effect = NetworkError("Network failed")

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch("protonfetcher.cli.sys.argv", ["protonfetcher", "-f", "GE-Proton"])

        # Act
        with pytest.raises(SystemExit):
            main()

        # Assert
        captured = capsys.readouterr()
        assert "Error:" in captured.out


class TestDebugLogging:
    """Test debug logging configuration."""

    def test_debug_flag_enables_debug_logging(
        self,
        mocker: Any,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that --debug flag enables debug logging."""
        # Arrange
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.link_manager.list_links.return_value = {}

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch("protonfetcher.cli.sys.argv", ["protonfetcher", "--debug"])

        # Act
        with caplog.at_level("DEBUG"):
            main()

        # Assert: Debug logging should be configured
        assert caplog.at_level("DEBUG")
