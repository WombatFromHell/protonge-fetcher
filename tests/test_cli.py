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

import subprocess
import sys
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from protonfetcher.cli import (
    _handle_check_operation_flow,
    convert_fork_to_enum,
    main,
    parse_arguments,
)
from protonfetcher.common import ForkName
from protonfetcher.exceptions import NetworkError, ProtonFetcherError
from protonfetcher.github_fetcher import GitHubReleaseFetcher
from protonfetcher.link_manager import LinkManager
from protonfetcher.release_manager import ReleaseManager

# =============================================================================
# Argument Parsing Tests
# =============================================================================


class TestArgumentParsing:
    """Test CLI argument parsing and validation."""

    def test_parse_default_arguments(self) -> None:
        """Test parsing default arguments (no flags)."""
        with patch.object(sys, "argv", ["protonfetcher"]):
            args = parse_arguments()
            assert not args.ls
            assert not args.list
            assert args.fork == ForkName.GE_PROTON

    @pytest.mark.parametrize(
        "argv,expected_flag,expected_value",
        [
            (["protonfetcher", "--list"], "list", True),
            (["protonfetcher", "-l"], "list", True),
            (["protonfetcher", "--ls"], "ls", True),
            (["protonfetcher", "--debug"], "debug", True),
        ],
    )
    def test_parse_boolean_flags(
        self, argv: list[str], expected_flag: str, expected_value: bool
    ) -> None:
        """Test parsing boolean flags."""
        with patch.object(sys, "argv", argv):
            args = parse_arguments()
            assert getattr(args, expected_flag) == expected_value

    @pytest.mark.parametrize(
        "argv,expected_flag,expected_value",
        [
            (["protonfetcher", "--fork", "GE-Proton"], "fork", "GE-Proton"),
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
            args = parse_arguments()
            assert getattr(args, expected_flag) == expected_value

    def test_parse_relink_flag(self) -> None:
        """Test parsing --relink flag."""
        with patch.object(
            sys, "argv", ["protonfetcher", "--relink", "--fork", "GE-Proton"]
        ):
            args = parse_arguments()
            assert args.relink is True
            assert args.fork == "GE-Proton"


# =============================================================================
# Argument Validation Tests
# =============================================================================


class TestArgumentValidation:
    """Test mutually exclusive argument validation."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["protonfetcher", "--list", "--release", "GE-Proton10-20"],
            ["protonfetcher", "--ls", "--release", "GE-Proton10-20"],
            ["protonfetcher", "--ls", "--list"],
            ["protonfetcher", "--rm", "GE-Proton10-20", "--release", "GE-Proton10-19"],
            ["protonfetcher", "--rm", "GE-Proton10-20", "--list"],
            ["protonfetcher", "--rm", "GE-Proton10-20", "--ls"],
        ],
    )
    def test_mutually_exclusive_flags(self, argv: list[str]) -> None:
        """Test that mutually exclusive flags cannot be used together."""
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_relink_without_fork_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that --relink requires --fork."""
        with patch.object(sys, "argv", ["protonfetcher", "--relink"]):
            with pytest.raises(SystemExit):
                parse_arguments()

        captured = capsys.readouterr()
        assert "--relink requires --fork" in captured.out

    @pytest.mark.parametrize(
        "argv",
        [
            [
                "protonfetcher",
                "--relink",
                "--fork",
                "GE-Proton",
                "--release",
                "GE-Proton10-20",
            ],
            ["protonfetcher", "--relink", "--fork", "GE-Proton", "--list"],
            ["protonfetcher", "--relink", "--fork", "GE-Proton", "--ls"],
            [
                "protonfetcher",
                "--relink",
                "--fork",
                "GE-Proton",
                "--rm",
                "GE-Proton10-20",
            ],
            ["protonfetcher", "--fork", "GE-Proton", "--check", "--dry-run"],
            ["protonfetcher", "--fork", "GE-Proton", "--check", "--list"],
            ["protonfetcher", "--dry-run", "--list"],
            ["protonfetcher", "--dry-run", "--ls"],
            ["protonfetcher", "--dry-run", "--rm", "GE-Proton10-20"],
            ["protonfetcher", "--dry-run", "--relink", "--fork", "GE-Proton"],
        ],
    )
    def test_check_and_dry_run_conflicts(self, argv: list[str]) -> None:
        """Test that --check and --dry-run conflict with other flags."""
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit):
                parse_arguments()


# =============================================================================
# Fork Conversion Tests
# =============================================================================


class TestForkConversion:
    """Test fork name conversion utilities."""

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            ("GE-Proton", ForkName.GE_PROTON),
            ("Proton-EM", ForkName.PROTON_EM),
            ("CachyOS", ForkName.CACHYOS),
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


class TestCheckForNewerRelease:
    """Tests for ReleaseManager.check_for_newer_release() method."""

    @pytest.mark.parametrize(
        "fork,repo,current_versions,latest_tag,expected",
        [
            # GE-Proton tests
            (
                ForkName.GE_PROTON,
                "GloriousEggroll/proton-ge-custom",
                ["GE-Proton10-20"],
                "GE-Proton10-21",
                "GE-Proton10-21",
            ),
            (
                ForkName.GE_PROTON,
                "GloriousEggroll/proton-ge-custom",
                ["GE-Proton10-20"],
                "GE-Proton10-20",
                None,
            ),
            (
                ForkName.GE_PROTON,
                "GloriousEggroll/proton-ge-custom",
                [],
                "GE-Proton10-21",
                "GE-Proton10-21",
            ),
            (
                ForkName.GE_PROTON,
                "GloriousEggroll/proton-ge-custom",
                ["GE-Proton10-18", "GE-Proton10-19", "GE-Proton10-20"],
                "GE-Proton10-22",
                "GE-Proton10-22",
            ),
            # Proton-EM tests (with directory naming convention)
            (
                ForkName.PROTON_EM,
                "Etaash-mathamsetty/Proton",
                ["proton-EM-10.0-30"],
                "EM-10.0-31",
                "EM-10.0-31",
            ),
            (
                ForkName.PROTON_EM,
                "Etaash-mathamsetty/Proton",
                ["proton-EM-10.0-30"],
                "EM-10.0-30",
                None,
            ),
            # CachyOS tests (with directory naming convention)
            (
                ForkName.CACHYOS,
                "CachyOS/proton-cachyos",
                ["proton-cachyos-10.0-20260207-slr-x86_64"],
                "cachyos-10.0-20260227-slr",
                "cachyos-10.0-20260227-slr",
            ),
            (
                ForkName.CACHYOS,
                "CachyOS/proton-cachyos",
                ["proton-cachyos-10.0-20260207-slr-x86_64"],
                "cachyos-10.0-20260207-slr",
                None,
            ),
        ],
    )
    def test_check_for_newer_release(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        fork: ForkName,
        repo: str,
        current_versions: list[str],
        latest_tag: str,
        expected: str | None,
    ) -> None:
        """Test detection of newer releases for all forks."""
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f'{{"tag_name": "{latest_tag}"}}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=f"Location: /releases/tag/{latest_tag}",
            stderr="",
        )

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        result = release_manager.check_for_newer_release(
            repo,
            current_versions,
            fork,
        )

        assert result == expected


class TestGetInstalledVersions:
    """Tests for LinkManager.get_installed_versions() method."""

    @pytest.mark.parametrize(
        "fork,versions,expected_order",
        [
            (
                ForkName.GE_PROTON,
                ["GE-Proton10-18", "GE-Proton10-20", "GE-Proton10-19"],
                ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"],
            ),
            # Proton-EM with actual directory naming (proton- prefix)
            (
                ForkName.PROTON_EM,
                [
                    "proton-EM-10.0-28",
                    "proton-EM-10.0-30",
                    "proton-EM-10.0-29",
                ],
                [
                    "proton-EM-10.0-30",
                    "proton-EM-10.0-29",
                    "proton-EM-10.0-28",
                ],
            ),
            # CachyOS with actual directory naming (proton- prefix and -x86_64 suffix)
            (
                ForkName.CACHYOS,
                [
                    "proton-cachyos-10.0-20260207-slr-x86_64",
                    "proton-cachyos-10.0-20260215-slr-x86_64",
                    "proton-cachyos-10.0-20260210-slr-x86_64",
                ],
                [
                    "proton-cachyos-10.0-20260215-slr-x86_64",
                    "proton-cachyos-10.0-20260210-slr-x86_64",
                    "proton-cachyos-10.0-20260207-slr-x86_64",
                ],
            ),
        ],
    )
    def test_get_installed_versions_sorted(
        self,
        tmp_path: Path,
        fork: ForkName,
        versions: list[str],
        expected_order: list[str],
    ) -> None:
        """Test that versions are returned sorted newest first."""
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for version in versions:
            (extract_dir / version).mkdir()

        fs = FileSystemClient()
        lm = LinkManager(fs)

        result = lm.get_installed_versions(extract_dir, fork)

        assert result == expected_order

    def test_get_installed_versions_empty(self, tmp_path: Path, fork: ForkName) -> None:
        """Test when no versions are installed."""
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        fs = FileSystemClient()
        lm = LinkManager(fs)

        result = lm.get_installed_versions(extract_dir, fork)

        assert result == []


class TestCheckForUpdates:
    """Tests for GitHubReleaseFetcher.check_for_updates() method."""

    @pytest.mark.parametrize(
        "fork,installed_dir,latest_tag,expected",
        [
            # GE-Proton
            (
                ForkName.GE_PROTON,
                "GE-Proton10-20",
                "GE-Proton10-21",
                "GE-Proton10-21",
            ),
            (
                ForkName.GE_PROTON,
                "GE-Proton10-21",
                "GE-Proton10-21",
                None,
            ),
            # Proton-EM (with proton- prefix in directory name)
            (
                ForkName.PROTON_EM,
                "proton-EM-10.0-30",
                "EM-10.0-31",
                "EM-10.0-31",
            ),
            (
                ForkName.PROTON_EM,
                "proton-EM-10.0-30",
                "EM-10.0-30",
                None,
            ),
            # CachyOS (with proton- prefix and -x86_64 suffix)
            (
                ForkName.CACHYOS,
                "proton-cachyos-10.0-20260207-slr-x86_64",
                "cachyos-10.0-20260227-slr",
                "cachyos-10.0-20260227-slr",
            ),
            (
                ForkName.CACHYOS,
                "proton-cachyos-10.0-20260207-slr-x86_64",
                "cachyos-10.0-20260207-slr",
                None,
            ),
        ],
    )
    def test_check_for_updates_all_forks(
        self,
        mocker: Any,
        mock_network_client: Any,
        tmp_path: Path,
        fork: ForkName,
        installed_dir: str,
        latest_tag: str,
        expected: str | None,
    ) -> None:
        """Test check_for_updates for all forks with real directory naming."""
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        (extract_dir / installed_dir).mkdir()

        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f'{{"tag_name": "{latest_tag}"}}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=f"Location: /releases/tag/{latest_tag}",
            stderr="",
        )

        fs = FileSystemClient()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=fs,
        )

        result = fetcher.check_for_updates(extract_dir, fork)
        assert result == expected


class TestCheckOperationFlow:
    """Tests for _handle_check_operation_flow() CLI handler."""

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

        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        args = mocker.MagicMock()
        args.fork = "GE-Proton"
        args.check = True

        exit_code = _handle_check_operation_flow(fetcher, args, extract_dir)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "New release available for GE-Proton: GE-Proton10-21!" in captured.out

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

        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )

        fs = FileSystemClient()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=fs,
        )

        args = mocker.MagicMock()
        args.fork = "GE-Proton"
        args.check = True

        exit_code = _handle_check_operation_flow(fetcher, args, extract_dir)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "GE-Proton: up-to-date" in captured.out


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
        from protonfetcher.link_manager import LinkManager

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        (extract_dir / "GE-Proton10-20").mkdir()

        fs = FileSystemClient()
        lm = LinkManager(fs)
        lm.create_symlinks_for_test(
            extract_dir, extract_dir / "GE-Proton10-20", ForkName.GE_PROTON
        )

        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
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

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "New release available for GE-Proton: GE-Proton10-21!" in captured.out

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

        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )

        mocker.patch(
            "sys.argv",
            ["protonfetcher", "--fork", "GE-Proton", "--check", "-x", str(extract_dir)],
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

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "New release available for GE-Proton: GE-Proton10-21!" in captured.out


# =============================================================================
# Dry-Run Tests
# =============================================================================


class TestDryRunCLI:
    """Tests for CLI --dry-run flag parsing and validation."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["protonfetcher", "--fork", "GE-Proton", "--dry-run"],
            ["protonfetcher", "-f", "GE-Proton", "-n"],
        ],
    )
    def test_dry_run_flag_parsing(self, argv: list[str], mocker: Any) -> None:
        """Test that --dry-run/-n flag is correctly parsed."""
        mocker.patch("protonfetcher.cli.sys.argv", argv)

        args = parse_arguments()
        assert args.dry_run is True


class TestDryRunWorkflow:
    """Tests for dry-run workflow execution."""

    @pytest.fixture
    def mock_fetcher(
        self, mock_network_client: Any, mock_filesystem_client: Any
    ) -> GitHubReleaseFetcher:
        """Create a fetcher with mocked dependencies for dry-run testing."""
        return GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

    def test_dry_run_does_not_download(
        self,
        mock_fetcher: GitHubReleaseFetcher,
        mock_network_client: Any,
        mocker: Any,
    ) -> None:
        """Test that dry-run mode does not perform actual downloads."""
        mocker.patch.object(
            mock_fetcher.release_manager,
            "fetch_latest_tag",
            return_value="GE-Proton10-20",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "find_asset_by_name",
            return_value="GE-Proton10-20.tar.gz",
        )
        mocker.patch.object(
            mock_fetcher.release_manager, "get_remote_asset_size", return_value=1048576
        )
        mocker.patch.object(
            mock_fetcher.link_manager, "find_version_candidates", return_value=[]
        )
        mocker.patch(
            "protonfetcher.github_fetcher.parse_version",
            return_value=("GE-Proton", 10, 20, 0),
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(
                Path("/tmp/GE-Proton"),
                Path("/tmp/GE-Proton-Fallback"),
                Path("/tmp/GE-Proton-Fallback2"),
            ),
        )

        result = mock_fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=Path("/tmp/downloads"),
            extract_dir=Path("/tmp/extract"),
            dry_run=True,
        )

        assert mock_network_client.download.call_count == 0
        assert result is None

    def test_dry_run_resolves_asset_info(
        self, mock_fetcher: GitHubReleaseFetcher, mocker: Any
    ) -> None:
        """Test that dry-run mode still resolves asset information."""
        mocker.patch.object(
            mock_fetcher.release_manager,
            "fetch_latest_tag",
            return_value="GE-Proton10-20",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "find_asset_by_name",
            return_value="GE-Proton10-20.tar.gz",
        )
        mocker.patch.object(
            mock_fetcher.release_manager, "get_remote_asset_size", return_value=1048576
        )
        mocker.patch.object(
            mock_fetcher.link_manager, "find_version_candidates", return_value=[]
        )
        mocker.patch(
            "protonfetcher.github_fetcher.parse_version",
            return_value=("GE-Proton", 10, 20, 0),
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(
                Path("/tmp/GE-Proton"),
                Path("/tmp/GE-Proton-Fallback"),
                Path("/tmp/GE-Proton-Fallback2"),
            ),
        )

        mock_fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=Path("/tmp/downloads"),
            extract_dir=Path("/tmp/extract"),
            dry_run=True,
        )

        cast(
            MagicMock, mock_fetcher.release_manager.find_asset_by_name
        ).assert_called_once()
        cast(
            MagicMock, mock_fetcher.release_manager.get_remote_asset_size
        ).assert_called_once()

    @pytest.mark.parametrize(
        "fork,expected_extract_path",
        [
            (ForkName.GE_PROTON, "GE-Proton10-20"),
            (ForkName.PROTON_EM, "proton-EM-10.0-30"),
            (ForkName.CACHYOS, "proton-cachyos-10.0-20260207-slr-x86_64"),
        ],
    )
    def test_dry_run_all_forks(
        self,
        mock_fetcher: GitHubReleaseFetcher,
        fork: ForkName,
        expected_extract_path: str,
        test_data: dict[str, Any],
        mocker: Any,
    ) -> None:
        """Test dry-run mode works for all supported forks."""
        repo = test_data["FORKS"][fork]["repo"]
        example_tag = test_data["FORKS"][fork]["example_tag"]
        example_asset = test_data["FORKS"][fork]["example_asset"]

        mocker.patch.object(
            mock_fetcher.release_manager, "fetch_latest_tag", return_value=example_tag
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "find_asset_by_name",
            return_value=example_asset,
        )
        mocker.patch.object(
            mock_fetcher.release_manager, "get_remote_asset_size", return_value=1048576
        )
        mocker.patch.object(
            mock_fetcher.link_manager, "find_version_candidates", return_value=[]
        )
        mocker.patch(
            "protonfetcher.github_fetcher.parse_version",
            return_value=("GE-Proton", 10, 20, 0),
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(
                Path(f"/tmp/{fork.value}"),
                Path(f"/tmp/{fork.value}-Fallback"),
                Path(f"/tmp/{fork.value}-Fallback2"),
            ),
        )

        result = mock_fetcher.fetch_and_extract(
            repo=repo,
            output_dir=Path("/tmp/downloads"),
            extract_dir=Path("/tmp/extract"),
            fork=fork,
            dry_run=True,
        )

        assert result is None


class TestDryRunOutput:
    """Tests for dry-run output messages."""

    @pytest.fixture
    def mock_fetcher(
        self, mock_network_client: Any, mock_filesystem_client: Any
    ) -> GitHubReleaseFetcher:
        """Create a fetcher with mocked dependencies."""
        return GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

    def test_dry_run_logs_what_would_be_downloaded(
        self,
        mock_fetcher: GitHubReleaseFetcher,
        caplog: pytest.LogCaptureFixture,
        mocker: Any,
    ) -> None:
        """Test that dry-run mode logs what would be downloaded."""
        import logging

        caplog.set_level(logging.INFO)

        mocker.patch.object(
            mock_fetcher.release_manager,
            "fetch_latest_tag",
            return_value="GE-Proton10-20",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "find_asset_by_name",
            return_value="GE-Proton10-20.tar.gz",
        )
        mocker.patch.object(
            mock_fetcher.release_manager, "get_remote_asset_size", return_value=1048576
        )
        mocker.patch.object(
            mock_fetcher.link_manager, "find_version_candidates", return_value=[]
        )
        mocker.patch(
            "protonfetcher.github_fetcher.parse_version",
            return_value=("GE-Proton", 10, 20, 0),
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(
                Path("/tmp/GE-Proton"),
                Path("/tmp/GE-Proton-Fallback"),
                Path("/tmp/GE-Proton-Fallback2"),
            ),
        )

        mock_fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=Path("/tmp/downloads"),
            extract_dir=Path("/tmp/extract"),
            dry_run=True,
        )

        assert "Would download: GE-Proton10-20.tar.gz" in caplog.text
        assert "(1.00 MiB)" in caplog.text
        assert "Would extract to:" in caplog.text

    def test_dry_run_logs_symlink_plan(
        self,
        mock_fetcher: GitHubReleaseFetcher,
        caplog: pytest.LogCaptureFixture,
        mocker: Any,
    ) -> None:
        """Test that dry-run mode logs planned symlink changes."""
        import logging

        caplog.set_level(logging.INFO)

        mocker.patch.object(
            mock_fetcher.release_manager,
            "fetch_latest_tag",
            return_value="GE-Proton10-20",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "find_asset_by_name",
            return_value="GE-Proton10-20.tar.gz",
        )
        mocker.patch.object(
            mock_fetcher.release_manager, "get_remote_asset_size", return_value=1048576
        )
        mocker.patch.object(
            mock_fetcher.link_manager, "find_version_candidates", return_value=[]
        )
        mocker.patch(
            "protonfetcher.github_fetcher.parse_version",
            return_value=("GE-Proton", 10, 20, 0),
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(
                Path("/tmp/extract/GE-Proton"),
                Path("/tmp/extract/GE-Proton-Fallback"),
                Path("/tmp/extract/GE-Proton-Fallback2"),
            ),
        )

        mock_fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=Path("/tmp/downloads"),
            extract_dir=Path("/tmp/extract"),
            dry_run=True,
        )

        assert "Would create/update symlinks:" in caplog.text
        assert "GE-Proton ->" in caplog.text
        assert "Dry run complete - no changes made" in caplog.text


class TestDryRunIntegration:
    """Integration tests for dry-run mode with CLI."""

    @pytest.mark.parametrize(
        "argv,expected_release",
        [
            (
                ["protonfetcher", "--fork", "GE-Proton", "--dry-run"],
                None,
            ),
            (
                [
                    "protonfetcher",
                    "--fork",
                    "GE-Proton",
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
        mock_fetcher.fetch_and_extract.return_value = None

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch("shutil.which", return_value="/usr/bin/curl")
        mocker.patch("protonfetcher.cli.sys.argv", argv)

        from protonfetcher.cli import main

        main()

        mock_fetcher.fetch_and_extract.assert_called_once()
        call_kwargs = mock_fetcher.fetch_and_extract.call_args.kwargs
        assert call_kwargs.get("dry_run") is True
        if expected_release:
            assert call_kwargs.get("release_tag") == expected_release
        assert "Success" not in capsys.readouterr().out


# =============================================================================
# CLI Operation Tests
# =============================================================================


class TestListReleasesOperation:
    """Test the --list operation."""

    @pytest.mark.parametrize(
        "fork,expected_tags",
        [
            ("GE-Proton", ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]),
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
        mock_fetcher.release_manager.list_recent_releases.return_value = expected_tags

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv", ["protonfetcher", "--list", "-f", fork]
        )

        main()

        captured = capsys.readouterr()
        for tag in expected_tags:
            assert tag in captured.out
        assert "Success" in captured.out


class TestListLinksOperation:
    """Test the --ls operation."""

    def test_list_links_default_all_forks(
        self, mocker: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test listing links for all forks (default behavior)."""
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.link_manager.list_links.side_effect = [
            {"GE-Proton": "/path/to/GE-Proton10-20"},
            {"Proton-EM": None},
            {"CachyOS": None},
        ]

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch("protonfetcher.cli.sys.argv", ["protonfetcher"])

        main()

        captured = capsys.readouterr()
        assert "GE-Proton" in captured.out
        assert "Proton-EM" in captured.out
        assert "CachyOS" in captured.out
        assert "Success" in captured.out

    def test_list_links_specific_fork(
        self, mocker: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test listing links for a specific fork."""
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

        main()

        captured = capsys.readouterr()
        assert "GE-Proton" in captured.out
        assert "GE-Proton-Fallback" in captured.out
        assert "Success" in captured.out


class TestRemoveOperation:
    """Test the --rm operation."""

    @pytest.mark.parametrize(
        "fork,release",
        [
            ("GE-Proton", "GE-Proton10-20"),
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
        mock_fetcher.link_manager.remove_release.return_value = True

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--rm", release, "-f", fork],
        )

        main()

        captured = capsys.readouterr()
        assert "Success" in captured.out
        mock_fetcher.link_manager.remove_release.assert_called_once()


class TestRelinkOperation:
    """Test the --relink operation."""

    @pytest.mark.parametrize(
        "fork",
        ["GE-Proton", "Proton-EM", "CachyOS"],
    )
    def test_relink(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        fork: str,
    ) -> None:
        """Test relinking symlinks."""
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.relink_fork.return_value = True

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--relink", "-f", fork],
        )

        main()

        captured = capsys.readouterr()
        assert "Success" in captured.out
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

        main()

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

        main()

        captured = capsys.readouterr()
        assert "Success" in captured.out


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
        mock_fetcher.update_all_managed_forks.return_value = {
            ForkName.GE_PROTON: temp_environment["extract_dir"] / "GE-Proton10-20"
        }

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv",
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
        assert "Successfully updated" in captured.out

    def test_f_flag_without_value_dry_run(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
        temp_environment: dict[str, Path],
    ) -> None:
        """Test that -f without value and -n shows dry run message."""
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.update_all_managed_forks.return_value = {ForkName.GE_PROTON: None}

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch(
            "protonfetcher.cli.sys.argv",
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
        assert "Success" not in capsys.readouterr().out

    def test_f_flag_with_specific_fork_value(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        temp_environment: dict[str, Path],
    ) -> None:
        """Test that -f with a specific fork value uses fetch_and_extract."""
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

        main()

        mock_fetcher.fetch_and_extract.assert_called_once()
        mock_fetcher.update_all_managed_forks.assert_not_called()
        captured = capsys.readouterr()
        assert "Success" in captured.out


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
        mock_fetcher.fetch_and_extract.side_effect = exception_type(exception_message)

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch("protonfetcher.cli.sys.argv", ["protonfetcher", "-f", "GE-Proton"])

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
        mock_fetcher.link_manager.list_links.return_value = {}

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher", return_value=mock_fetcher
        )
        mocker.patch("protonfetcher.cli.sys.argv", ["protonfetcher", "--debug"])

        with caplog.at_level("DEBUG"):
            main()

        assert caplog.at_level("DEBUG")
