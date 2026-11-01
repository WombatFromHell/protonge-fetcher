"""
CLI tests for ProtonFetcher.

Consolidated tests for the command-line interface including:
- Argument parsing and validation
- Check mode (--check/-c)
- Dry-run mode (--dry-run/-n)
- List operations (--list, --ls)
- Remove operation (--rm)
- Relink operation (--relink)
- Download operation (default)
- Multi-fork update mode (-f without value)
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from protonfetcher.cli.argparse_builder import build_parser, parse_args
from protonfetcher.cli.core import _instance_lock, main
from protonfetcher.cli.fork_utils import convert_fork_to_enum
from protonfetcher.cli.handlers import handle_check_operation
from protonfetcher.cli.validators import (
    set_default_fork,
    validate_mutually_exclusive_args,
)
from protonfetcher.common import ForkName
from protonfetcher.dirs import get_link_names, lock_path
from protonfetcher.common import HttpResponse
from protonfetcher.exceptions import NetworkError, ProtonFetcherError
from protonfetcher.github_fetcher import GitHubReleaseFetcher
from protonfetcher.link_manager import LinkManager

# =============================================================================
# Argument Parsing Tests
# =============================================================================


class TestArgumentParsing:
    """Test CLI argument parsing and validation."""

    def test_parse_default_arguments(self) -> None:
        """Test parsing default arguments (no flags)."""
        with patch.object(sys, "argv", ["protonfetcher"]):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            assert not args.ls
            assert not args.list
            assert not args.skip_checksum
            assert args.fork == ForkName.GE_PROTON

    @pytest.mark.parametrize(
        "argv,expected_flag,expected_value",
        [
            (["protonfetcher", "--list"], "list", True),
            (["protonfetcher", "-l"], "list", True),
            (["protonfetcher", "--ls"], "ls", True),
            (["protonfetcher", "--debug"], "debug", True),
            (["protonfetcher", "--skip-checksum"], "skip_checksum", True),
        ],
    )
    def test_parse_boolean_flags(
        self, argv: list[str], expected_flag: str, expected_value: bool
    ) -> None:
        """Test parsing boolean flags."""
        with patch.object(sys, "argv", argv):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            assert getattr(args, expected_flag) == expected_value

    @pytest.mark.parametrize(
        "argv,expected_flag,expected_value",
        [
            (["protonfetcher", "--fork", "Proton-GE"], "fork", "Proton-GE"),
            (["protonfetcher", "-f", "Proton-EM"], "fork", "Proton-EM"),
            (
                ["protonfetcher", "--release", "GE-Proton10-15"],
                "release",
                "GE-Proton10-15",
            ),
            (["protonfetcher", "-r", "EM-10.0-30"], "release", "EM-10.0-30"),
            (
                ["protonfetcher", "--extract-dir", "/custom/path"],
                "extract_dir",
                "/custom/path",
            ),
            (["protonfetcher", "-x", "/another/path"], "extract_dir", "/another/path"),
            (["protonfetcher", "--output", "/downloads"], "output", "/downloads"),
            (["protonfetcher", "-o", "/tmp"], "output", "/tmp"),
        ],
    )
    def test_parse_value_flags(
        self, argv: list[str], expected_flag: str, expected_value: str
    ) -> None:
        """Test parsing flags with values."""
        with patch.object(sys, "argv", argv):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            assert getattr(args, expected_flag) == expected_value

    def test_parse_rm_with_link_name(self) -> None:
        """Test --rm with an optional link alias value, and bare --rm."""
        with patch.object(
            sys, "argv", ["protonfetcher", "-f", "Proton-GE", "--rm", "Proton-GE"]
        ):
            args = parse_args(build_parser())
            assert args.rm == "Proton-GE"
            assert args.fork == "Proton-GE"

        with patch.object(sys, "argv", ["protonfetcher", "--rm"]):
            args = parse_args(build_parser())
            assert args.rm is True

    def test_parse_relink_flag(self) -> None:
        """Test parsing --relink flag."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--relink", "--fork", "Proton-GE"]
        ):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            assert args.relink is True
            assert args.fork == "Proton-GE"


# =============================================================================
# Argument Validation Tests
# =============================================================================


class TestArgumentValidation:
    """Test mutually exclusive argument validation."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["protonfetcher", "--ls", "--list"],
        ],
    )
    def test_mutually_exclusive_flags(self, argv: list[str]) -> None:
        """Test that mutually exclusive flags cannot be used together."""
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit):
                parse_args(build_parser())

    def test_relink_without_fork_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that --relink requires --fork."""
        with patch.object(sys, "argv", ["protonfetcher", "--relink"]):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            with pytest.raises(SystemExit):
                validate_mutually_exclusive_args(args)

        captured = capsys.readouterr()
        assert "--relink requires --fork" in captured.out

    @pytest.mark.parametrize(
        "argv",
        [
            ["protonfetcher", "--relink", "--fork", "Proton-GE", "--list"],
            ["protonfetcher", "--relink", "--fork", "Proton-GE", "--ls"],
            ["protonfetcher", "--fork", "Proton-GE", "--check", "--dry-run"],
            ["protonfetcher", "--fork", "Proton-GE", "--check", "--list"],
            ["protonfetcher", "--dry-run", "--list"],
            ["protonfetcher", "--dry-run", "--ls"],
            ["protonfetcher", "--dry-run", "--relink", "--fork", "Proton-GE"],
        ],
    )
    def test_check_and_dry_run_conflicts(self, argv: list[str]) -> None:
        """Test that --check and --dry-run conflict with other flags."""
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit):
                args = parse_args(build_parser())
                args = set_default_fork(args)
                validate_mutually_exclusive_args(args)


# =============================================================================
# Fork Conversion Tests
# =============================================================================


class TestForkConversion:
    """Test fork name conversion utilities."""

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            ("Proton-GE", ForkName.GE_PROTON),
            ("Proton-EM", ForkName.PROTON_EM),
            ("Proton-CachyOS", ForkName.CACHYOS),
            (ForkName.GE_PROTON, ForkName.GE_PROTON),
            (ForkName.PROTON_EM, ForkName.PROTON_EM),
            (None, ForkName.GE_PROTON),
        ],
    )
    def test_convert_fork_valid(
        self, input_value: str | ForkName | None, expected: ForkName
    ) -> None:
        """Test converting valid fork strings to enum."""
        result = convert_fork_to_enum(input_value)
        assert result == expected

    def test_convert_invalid_string(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test converting invalid fork string."""
        with pytest.raises(SystemExit):
            convert_fork_to_enum("Invalid-Fork")

        captured = capsys.readouterr()
        assert "Invalid fork" in captured.out


# =============================================================================
# Check Mode Tests
# =============================================================================


class TestCheckOperationFlow:
    """Tests for handle_check_operation() CLI handler."""

    def test_check_single_fork_update_available(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test check operation for single fork with update available."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        (extract_dir / "GE-Proton10-20").mkdir()

        mock_network_client.get.return_value = HttpResponse(
            status=200, body='{"tag_name": "GE-Proton10-21"}'
        )
        mock_network_client.head.return_value = HttpResponse(
            status=200, final_url="/releases/tag/GE-Proton10-21"
        )

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        args = mocker.MagicMock()
        args.fork = "Proton-GE"
        args.check = True

        forgejo_fetcher = mocker.MagicMock()

        with pytest.raises(SystemExit) as exc_info:
            handle_check_operation(fetcher, forgejo_fetcher, args, extract_dir)
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "New release available for Proton-GE: GE-Proton10-21!" in captured.out

    def test_check_single_fork_up_to_date(
        self,
        mocker: Any,
        mock_network_client: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test check operation for single fork when up-to-date."""
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        (extract_dir / "GE-Proton10-21").mkdir()

        mock_network_client.get.return_value = HttpResponse(
            status=200, body='{"tag_name": "GE-Proton10-21"}'
        )
        mock_network_client.head.return_value = HttpResponse(
            status=200, final_url="/releases/tag/GE-Proton10-21"
        )

        fs = FileSystemClient()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=fs,
        )

        args = mocker.MagicMock()
        args.fork = "Proton-GE"
        args.check = True

        forgejo_fetcher = mocker.MagicMock()

        with pytest.raises(SystemExit) as exc_info:
            handle_check_operation(fetcher, forgejo_fetcher, args, extract_dir)
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "Proton-GE: up-to-date" in captured.out


class TestCheckCLI:
    """CLI tests for --check flag."""

    def test_check_flag_standalone_checks_all_managed_forks(
        self,
        mocker: Any,
        mock_network_client: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that --check alone checks all managed forks."""
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        (extract_dir / "GE-Proton10-20").mkdir()

        fs = FileSystemClient()
        lm = LinkManager(fs)
        main_link, fb1, fb2 = get_link_names(extract_dir, ForkName.GE_PROTON)
        lm.create_symlinks(
            main_link,
            fb1,
            fb2,
            [
                (("test", 0, 0, 0), extract_dir / "GE-Proton10-20"),
                (("test", 0, 0, 0), extract_dir / "GE-Proton10-20"),
                (("test", 0, 0, 0), extract_dir / "GE-Proton10-20"),
            ],
        )

        mock_network_client.get.return_value = HttpResponse(
            status=200, body='{"tag_name": "GE-Proton10-21"}'
        )
        mock_network_client.head.return_value = HttpResponse(
            status=200, final_url="/releases/tag/GE-Proton10-21"
        )

        mocker.patch(
            "sys.argv",
            ["protonfetcher", "--check", "-x", str(extract_dir)],
        )

        original_init = GitHubReleaseFetcher.__init__

        def mock_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.network_client = mock_network_client
            self.file_system_client = fs
            self.release_manager.network_client = mock_network_client
            self.release_manager.file_system_client = fs
            self.link_manager.file_system_client = fs

        mocker.patch.object(GitHubReleaseFetcher, "__init__", mock_init)

        # Mock ForgejoReleaseFetcher
        mock_forgejo = mocker.MagicMock()
        mock_forgejo.link_manager.has_managed_links.return_value = False
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher", return_value=mock_forgejo
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "New release available for Proton-GE: GE-Proton10-21!" in captured.out

    def test_check_flag_with_fork(
        self,
        mocker: Any,
        mock_network_client: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test --check flag with specific fork."""
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        (extract_dir / "GE-Proton10-20").mkdir()

        mock_network_client.get.return_value = HttpResponse(
            status=200, body='{"tag_name": "GE-Proton10-21"}'
        )
        mock_network_client.head.return_value = HttpResponse(
            status=200, final_url="/releases/tag/GE-Proton10-21"
        )

        mocker.patch(
            "sys.argv",
            ["protonfetcher", "--fork", "Proton-GE", "--check", "-x", str(extract_dir)],
        )

        fs = FileSystemClient()

        original_init = GitHubReleaseFetcher.__init__

        def mock_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.network_client = mock_network_client
            self.file_system_client = fs
            self.release_manager.network_client = mock_network_client
            self.release_manager.file_system_client = fs
            self.link_manager.file_system_client = fs

        mocker.patch.object(GitHubReleaseFetcher, "__init__", mock_init)

        # Mock ForgejoReleaseFetcher
        mock_forgejo = mocker.MagicMock()
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher", return_value=mock_forgejo
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "New release available for Proton-GE: GE-Proton10-21!" in captured.out


# =============================================================================
# Dry-Run Tests
# =============================================================================


class TestDryRunCLI:
    """Tests for CLI --dry-run flag parsing and validation."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["protonfetcher", "--fork", "Proton-GE", "--dry-run"],
            ["protonfetcher", "-f", "Proton-GE", "-n"],
        ],
    )
    def test_dry_run_flag_parsing(self, argv: list[str], mocker: Any) -> None:
        """Test that --dry-run/-n flag is correctly parsed."""
        mocker.patch("sys.argv", argv)

        args = parse_args(build_parser())
        args = set_default_fork(args)
        assert args.dry_run is True


class TestDryRunIntegration:
    """Integration tests for dry-run mode with CLI."""

    @pytest.mark.parametrize(
        "argv,expected_release",
        [
            (
                ["protonfetcher", "--fork", "Proton-GE", "--dry-run"],
                None,
            ),
            (
                [
                    "protonfetcher",
                    "--fork",
                    "Proton-GE",
                    "--release",
                    "GE-Proton10-20",
                    "--dry-run",
                ],
                "GE-Proton10-20",
            ),
        ],
    )
    def test_cli_dry_run(
        self,
        capsys: pytest.CaptureFixture[str],
        mocker: Any,
        argv: list[str],
        expected_release: str | None,
    ) -> None:
        """Test CLI --dry-run flag works end-to-end."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_and_extract.return_value = None

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch("shutil.which", return_value="/usr/bin/curl")
        mocker.patch("sys.argv", argv)

        from protonfetcher.cli.core import main

        main()

        mock_fetcher.fetch_and_extract.assert_called_once()
        call_kwargs = mock_fetcher.fetch_and_extract.call_args.kwargs
        assert call_kwargs.get("dry_run") is True
        if expected_release:
            assert call_kwargs.get("release_tag") == expected_release


# =============================================================================
# CLI Operation Tests
# =============================================================================


class TestListReleasesOperation:
    """Test the --list operation."""

    @pytest.mark.parametrize(
        "fork,expected_tags",
        [
            ("Proton-GE", ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]),
            ("Proton-EM", ["EM-10.0-30", "EM-10.0-29", "EM-10.0-28"]),
        ],
    )
    def test_list_releases(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        fork: str,
        expected_tags: list[str],
    ) -> None:
        """Test listing recent releases."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.list_recent_releases.return_value = expected_tags

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch("sys.argv", ["protonfetcher", "--list", "-f", fork])

        main()

        captured = capsys.readouterr()
        for tag in expected_tags:
            assert tag in captured.out


class TestListLinksOperation:
    """Test the --ls operation."""

    def test_list_links_default_all_forks(
        self, mocker: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test listing links for all forks (default behavior)."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()

        def list_links_side_effect(extract_dir, fork):
            if fork == ForkName.GE_PROTON:
                return {"Proton-GE": "/path/to/GE-Proton10-20"}
            elif fork == ForkName.PROTON_EM:
                return {"Proton-EM": None}
            elif fork == ForkName.CACHYOS:
                return {"Proton-CachyOS": None}
            elif fork == ForkName.DW_PROTON:
                return {"Proton-DW": None}
            return {}

        mock_fetcher.link_manager.list_links.side_effect = list_links_side_effect
        mock_forgejo_fetcher.link_manager.list_links.side_effect = (
            list_links_side_effect
        )
        # No prunable versions for any fork
        mock_fetcher.link_manager.get_installed_versions.return_value = []
        mock_fetcher.link_manager.get_linked_versions.return_value = []
        mock_forgejo_fetcher.link_manager.get_installed_versions.return_value = []
        mock_forgejo_fetcher.link_manager.get_linked_versions.return_value = []

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch("sys.argv", ["protonfetcher"])

        main()

        captured = capsys.readouterr()
        assert "Proton-GE" in captured.out  # has a symlink
        assert "Proton-EM" not in captured.out  # no symlinks, no prunable
        assert "Proton-CachyOS" not in captured.out  # no symlinks, no prunable
        assert "Proton-DW" not in captured.out  # no symlinks, no prunable

    def test_list_links_specific_fork(
        self, mocker: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test listing links for a specific fork."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.link_manager.list_links.return_value = {
            "Proton-GE": "/path/to/GE-Proton10-20",
            "Proton-GE-Fallback": "/path/to/GE-Proton10-19",
            "Proton-GE-Fallback2": "/path/to/GE-Proton10-18",
        }

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch("sys.argv", ["protonfetcher", "--ls", "-f", "Proton-GE"])

        main()

        captured = capsys.readouterr()
        assert "Proton-GE" in captured.out
        assert "Proton-GE-Fallback" in captured.out


class TestRemoveOperation:
    """Test the --rm operation."""

    @pytest.mark.parametrize(
        "fork,release",
        [
            ("Proton-GE", "GE-Proton10-20"),
            ("Proton-EM", "EM-10.0-30"),
        ],
    )
    def test_remove_release(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        fork: str,
        release: str,
    ) -> None:
        """Test removing a release."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.link_manager.remove_release.return_value = True

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch(
            "sys.argv",
            ["protonfetcher", "--rm", "--release", release, "-f", fork],
        )
        # Prevent cleanup from touching the real filesystem
        mocker.patch(
            "protonfetcher.cli.handlers._cleanup_stale_symlinks",
        )

        main()

        mock_fetcher.link_manager.remove_release.assert_called_once()


class TestRelinkOperation:
    """Test the --relink operation."""

    @pytest.mark.parametrize(
        "fork",
        ["Proton-GE", "Proton-EM", "Proton-CachyOS"],
    )
    def test_relink(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        fork: str,
    ) -> None:
        """Test relinking symlinks."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.relink_fork.return_value = True

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch(
            "sys.argv",
            ["protonfetcher", "--relink", "-f", fork],
        )

        main()

        mock_fetcher.relink_fork.assert_called_once()


class TestDownloadOperation:
    """Test the download operation."""

    def test_download_with_fork_flag(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        temp_environment: dict[str, Path],
    ) -> None:
        """Test downloading with --fork flag."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_and_extract.return_value = (
            temp_environment["extract_dir"] / "GE-Proton10-20"
        )

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch(
            "sys.argv",
            [
                "protonfetcher",
                "-f",
                "Proton-GE",
                "-x",
                str(temp_environment["extract_dir"]),
                "-o",
                str(temp_environment["output_dir"]),
            ],
        )

        main()

        mock_fetcher.fetch_and_extract.assert_called_once()

    def test_download_with_release_flag(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        temp_environment: dict[str, Path],
    ) -> None:
        """Test downloading specific release with --release flag."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_and_extract.return_value = (
            temp_environment["extract_dir"] / "GE-Proton10-15"
        )

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch(
            "sys.argv",
            [
                "protonfetcher",
                "-f",
                "Proton-GE",
                "-r",
                "GE-Proton10-15",
                "-x",
                str(temp_environment["extract_dir"]),
                "-o",
                str(temp_environment["output_dir"]),
            ],
        )

        main()


class TestForkFlagWithoutValue:
    """Test the -f flag without a value (multi-fork update mode)."""

    def test_f_flag_without_value_calls_update_all_managed_forks(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        temp_environment: dict[str, Path],
    ) -> None:
        """Test that -f without a value calls update_all_managed_forks."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.update_all_managed_forks.return_value = {
            ForkName.GE_PROTON: temp_environment["extract_dir"] / "GE-Proton10-20"
        }

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch(
            "sys.argv",
            [
                "protonfetcher",
                "-f",
                "-x",
                str(temp_environment["extract_dir"]),
                "-o",
                str(temp_environment["output_dir"]),
            ],
        )

        main()

        mock_fetcher.update_all_managed_forks.assert_called_once()
        captured = capsys.readouterr()
        assert "Done" in captured.out

    def test_f_flag_without_value_dry_run(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
        temp_environment: dict[str, Path],
    ) -> None:
        """Test that -f without value and -n shows dry run message."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.update_all_managed_forks.return_value = {ForkName.GE_PROTON: None}
        mock_forgejo_fetcher.link_manager.has_managed_links.return_value = False

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch(
            "sys.argv",
            [
                "protonfetcher",
                "-f",
                "-n",
                "-x",
                str(temp_environment["extract_dir"]),
                "-o",
                str(temp_environment["output_dir"]),
            ],
        )

        with caplog.at_level("INFO"):
            main()

        mock_fetcher.update_all_managed_forks.assert_called_once()
        call_kwargs = mock_fetcher.update_all_managed_forks.call_args.kwargs
        assert call_kwargs.get("dry_run") is True

    def test_f_flag_with_specific_fork_value(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        temp_environment: dict[str, Path],
    ) -> None:
        """Test that -f with a specific fork value uses fetch_and_extract."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_and_extract.return_value = (
            temp_environment["extract_dir"] / "GE-Proton10-20"
        )

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch(
            "sys.argv",
            [
                "protonfetcher",
                "-f",
                "Proton-GE",
                "-x",
                str(temp_environment["extract_dir"]),
                "-o",
                str(temp_environment["output_dir"]),
            ],
        )

        main()

        mock_fetcher.fetch_and_extract.assert_called_once()
        mock_fetcher.update_all_managed_forks.assert_not_called()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test CLI error handling."""

    @pytest.mark.parametrize(
        "exception_type,exception_message",
        [
            (ProtonFetcherError, "Test error message"),
            (NetworkError, "Network failed"),
        ],
    )
    def test_error_handling(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        exception_type: type[Exception],
        exception_message: str,
    ) -> None:
        """Test handling of ProtonFetcherError and NetworkError."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_and_extract.side_effect = exception_type(exception_message)

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch("sys.argv", ["protonfetcher", "-f", "Proton-GE"])

        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert exception_message in captured.out


class TestDebugLogging:
    """Test debug logging configuration."""

    def test_debug_flag_enables_debug_logging(
        self,
        mocker: Any,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that --debug flag enables debug logging."""
        mock_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_fetcher.link_manager.list_links.return_value = {}

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch("sys.argv", ["protonfetcher", "--debug"])

        with caplog.at_level("DEBUG"):
            main()

        assert caplog.at_level("DEBUG")


# =============================================================================
# ForkConfig.platform Dispatch Tests (Phase 2.4)
# =============================================================================


class TestForkConfigPlatformDispatch:
    """Tests verifying ForkConfig.platform drives correct fetcher dispatch."""

    def test_dw_proton_uses_forgejo_fetcher(
        self,
        mocker: Any,
        capsys: Any,
    ) -> None:
        """Test that Proton-DW fork dispatches to ForgejoReleaseFetcher."""
        mock_forgejo_fetcher = mocker.MagicMock()
        mock_forgejo_fetcher.list_recent_releases.return_value = [
            "dwproton-10.0-26",
            "dwproton-10.0-25",
        ]

        mocker.patch(
            "protonfetcher.cli.core.ForgejoReleaseFetcher",
            return_value=mock_forgejo_fetcher,
        )
        mocker.patch("sys.argv", ["protonfetcher", "--list", "-f", "Proton-DW"])

        main()

        captured = capsys.readouterr()
        assert "dwproton-10.0-26" in captured.out
        mock_forgejo_fetcher.list_recent_releases.assert_called_once()

    def test_ge_proton_uses_github_fetcher(
        self,
        mocker: Any,
        capsys: Any,
    ) -> None:
        """Test that Proton-GE fork dispatches to GitHubReleaseFetcher."""
        mock_github_fetcher = mocker.MagicMock()
        mock_github_fetcher.list_recent_releases.return_value = [
            "GE-Proton10-20",
            "GE-Proton10-19",
        ]

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher",
            return_value=mock_github_fetcher,
        )
        mocker.patch("sys.argv", ["protonfetcher", "--list", "-f", "Proton-GE"])

        main()

        captured = capsys.readouterr()
        assert "GE-Proton10-20" in captured.out
        mock_github_fetcher.list_recent_releases.assert_called_once()

    def test_proton_em_uses_github_fetcher(
        self,
        mocker: Any,
        capsys: Any,
    ) -> None:
        """Test that Proton-EM fork dispatches to GitHubReleaseFetcher."""
        mock_github_fetcher = mocker.MagicMock()
        mock_github_fetcher.list_recent_releases.return_value = [
            "EM-10.0-30",
            "EM-10.0-29",
        ]

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher",
            return_value=mock_github_fetcher,
        )
        mocker.patch("sys.argv", ["protonfetcher", "--list", "-f", "Proton-EM"])

        main()

        captured = capsys.readouterr()
        assert "EM-10.0-30" in captured.out
        mock_github_fetcher.list_recent_releases.assert_called_once()

    def test_cachyos_uses_github_fetcher(
        self,
        mocker: Any,
        capsys: Any,
    ) -> None:
        """Test that CachyOS fork dispatches to GitHubReleaseFetcher."""
        mock_github_fetcher = mocker.MagicMock()
        mock_github_fetcher.list_recent_releases.return_value = [
            "cachyos-10.0-20260207-slr",
        ]

        mocker.patch(
            "protonfetcher.cli.core.GitHubReleaseFetcher",
            return_value=mock_github_fetcher,
        )
        mocker.patch("sys.argv", ["protonfetcher", "--list", "-f", "Proton-CachyOS"])

        main()

        captured = capsys.readouterr()
        assert "cachyos-10.0-20260207-slr" in captured.out
        mock_github_fetcher.list_recent_releases.assert_called_once()


class TestCliFileErrorReporting:
    """A filesystem error must be one readable line, not a traceback."""

    def test_os_error_prints_one_line_and_exits_1(
        self, mocker: Any, capsys: Any
    ) -> None:
        mocker.patch("sys.argv", ["protonfetcher", "--list"])
        mocker.patch(
            "protonfetcher.cli.core._dispatch",
            side_effect=IsADirectoryError(
                "Failed to create directory /x: is a directory"
            ),
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        assert (
            capsys.readouterr().out
            == "Error: Failed to create directory /x: is a directory\n"
        )


# =============================================================================
# Single-Instance Mutex Tests
# =============================================================================


class TestInstanceLock:
    """Test the whole-run mutex that refuses concurrent protonfetcher instances."""

    def test_lock_path_prefers_xdg_runtime_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        assert lock_path() == tmp_path / f"protonfetcher-{os.getuid()}.lock"

    def test_lock_path_falls_back_scoped_by_uid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ssh/cron sessions have no XDG_RUNTIME_DIR, so the root is /run/user/<uid> or /tmp."""
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        run_user = Path(f"/run/user/{os.getuid()}")
        root = run_user if run_user.is_dir() else Path(tempfile.gettempdir())
        assert lock_path() == root / f"protonfetcher-{os.getuid()}.lock"

    def test_lock_file_records_the_holder_pid(self) -> None:
        with _instance_lock():
            assert lock_path().read_text() == f"{os.getpid()}\n"

    def test_second_acquire_names_the_holder(self) -> None:
        with _instance_lock():
            with pytest.raises(ProtonFetcherError) as exc_info:
                with _instance_lock():
                    pass
            assert f"PID {os.getpid()}" in str(exc_info.value)

    def test_lock_releases_when_the_context_exits(self) -> None:
        with _instance_lock():
            pass
        with _instance_lock():
            pass

    def test_main_refuses_and_never_dispatches(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

        with _instance_lock():
            monkeypatch.setattr(sys, "argv", ["protonfetcher", "--check"])
            with patch("protonfetcher.cli.core._dispatch") as dispatch:
                with pytest.raises(SystemExit) as exc_info:
                    main()

            assert exc_info.value.code == 1
            dispatch.assert_not_called()
            assert capsys.readouterr().out == (
                f"Error: another protonfetcher (PID {os.getpid()}) is running\n"
            )


# =============================================================================
# Ctrl+C Handling
# =============================================================================


class TestInterruptHandling:
    """Ctrl+C must end with a message and a SIGINT exit code, not a traceback."""

    def test_main_exits_130_on_interrupt(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        monkeypatch.setattr(sys, "argv", ["protonfetcher", "--check"])

        with (
            patch("protonfetcher.cli.core.GitHubReleaseFetcher"),
            patch("protonfetcher.cli.core.ForgejoReleaseFetcher"),
            patch("protonfetcher.cli.core._dispatch", side_effect=KeyboardInterrupt),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 130
        assert capsys.readouterr().out == (
            "\nInterrupted. Partial downloads are kept — run again to resume.\n"
        )


# =============================================================================
# --skip-checksum Wiring
# =============================================================================


class TestSkipChecksumWiring:
    """The flag reaches the downloaders that actually verify."""

    @pytest.mark.parametrize(
        "argv,expected_verify",
        [
            (["protonfetcher", "--check"], True),
            (["protonfetcher", "--check", "--skip-checksum"], False),
        ],
    )
    def test_fetchers_get_the_verdict(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        argv: list[str],
        expected_verify: bool,
    ) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        monkeypatch.setattr(sys, "argv", argv)

        with (
            patch("protonfetcher.cli.core.GitHubReleaseFetcher") as github,
            patch("protonfetcher.cli.core.ForgejoReleaseFetcher") as forgejo,
            patch("protonfetcher.cli.core._dispatch"),
        ):
            main()

        github.assert_called_once_with(verify_checksum=expected_verify)
        forgejo.assert_called_once_with(verify_checksum=expected_verify)
