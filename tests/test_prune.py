"""
Tests for the --prune feature.

Tests the prune functionality including:
- Argument parsing and validation
- Prune operation flow (single fork and all forks)
- Dry-run mode
- Keep parameter
- Integration with LinkManager.prune_releases()
"""

from pathlib import Path
from typing import Any

import pytest

from protonfetcher.cli.argparse_builder import build_parser, parse_args
from protonfetcher.cli.handlers import handle_prune_operation
from protonfetcher.cli.validators import (
    set_default_fork,
    validate_mutually_exclusive_args,
)
from protonfetcher.common import ForkName
from protonfetcher.forgejo_fetcher import ForgejoReleaseFetcher
from protonfetcher.github_fetcher import GitHubReleaseFetcher

# =============================================================================
# Argument Parsing Tests
# =============================================================================


class TestPruneArgumentParsing:
    """Test CLI argument parsing for --prune flag."""

    def test_parse_prune_flag(self) -> None:
        """Test parsing --prune flag."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["protonfetcher", "--prune"]):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            assert args.prune is True
            assert args.keep == 1  # default

    def test_parse_prune_with_keep(self) -> None:
        """Test parsing --prune with --keep parameter."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["protonfetcher", "--prune", "--keep", "5"]):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            assert args.prune is True
            assert args.keep == 5

    def test_parse_prune_with_fork(self) -> None:
        """Test parsing --prune with --fork parameter."""
        import sys
        from unittest.mock import patch

        with patch.object(
            sys, "argv", ["protonfetcher", "--prune", "--fork", "Proton-EM"]
        ):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            assert args.prune is True
            assert args.fork == "Proton-EM"

    def test_parse_prune_with_dry_run(self) -> None:
        """Test parsing --prune with --dry-run flag."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["protonfetcher", "--prune", "--dry-run"]):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            assert args.prune is True
            assert args.dry_run is True

    def test_parse_prune_mutually_exclusive_with_release(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that --prune and --release are mutually exclusive."""
        import sys
        from unittest.mock import patch

        with patch.object(
            sys, "argv", ["protonfetcher", "--prune", "--release", "GE-Proton10-20"]
        ):
            with pytest.raises(SystemExit) as exc_info:
                parse_args(build_parser())
            # argparse uses exit code 2 for argument parsing errors
            assert exc_info.value.code == 2
            captured = capsys.readouterr()
            assert "not allowed with argument --prune" in captured.err

    def test_parse_prune_mutually_exclusive_with_list(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that --prune and --list are mutually exclusive."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["protonfetcher", "--prune", "--list"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_args(build_parser())
            # argparse uses exit code 2 for argument parsing errors
            assert exc_info.value.code == 2

    def test_parse_prune_mutually_exclusive_with_ls(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that --prune and --ls are mutually exclusive."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["protonfetcher", "--prune", "--ls"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_args(build_parser())
            # argparse uses exit code 2 for argument parsing errors
            assert exc_info.value.code == 2

    def test_parse_prune_and_rm_together(self) -> None:
        """Test that --prune and --rm can be used together."""
        import sys
        from unittest.mock import patch

        with patch.object(
            sys, "argv", ["protonfetcher", "--prune", "--rm", "GE-Proton10-20"]
        ):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            # Should parse successfully — no SystemExit
            assert args.prune is True
            assert args.rm == "GE-Proton10-20"

    def test_parse_prune_mutually_exclusive_with_relink(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that --prune and --relink are mutually exclusive."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["protonfetcher", "--prune", "--relink"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_args(build_parser())
            # argparse uses exit code 2 for argument parsing errors
            assert exc_info.value.code == 2

    def test_parse_prune_mutually_exclusive_with_check(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that --prune and --check are mutually exclusive."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["protonfetcher", "--prune", "--check"]):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            with pytest.raises(SystemExit) as exc_info:
                validate_mutually_exclusive_args(args)
            # Validation-level conflict uses exit code 1
            assert exc_info.value.code == 1

    def test_parse_prune_with_invalid_keep(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that --keep 0 is rejected."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["protonfetcher", "--prune", "--keep", "0"]):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            with pytest.raises(SystemExit) as exc_info:
                validate_mutually_exclusive_args(args)
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "--keep must be at least 1" in captured.out

    def test_parse_prune_with_negative_keep(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that --keep -1 is rejected."""
        import sys
        from unittest.mock import patch

        with patch.object(sys, "argv", ["protonfetcher", "--prune", "--keep", "-1"]):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            with pytest.raises(SystemExit) as exc_info:
                validate_mutually_exclusive_args(args)
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "--keep must be at least 1" in captured.out


# =============================================================================
# Prune Operation Flow Tests
# =============================================================================


class TestPruneOperationFlow:
    """Test the --prune operation flow."""

    def test_prune_no_unmanaged_releases(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test pruning when there are no unmanaged releases."""
        mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
        mock_forgejo_fetcher = mocker.MagicMock(spec=ForgejoReleaseFetcher)
        mock_fetcher.prune_releases.return_value = ([], [])
        mock_forgejo_fetcher.prune_releases.return_value = ([], [])

        args = mocker.MagicMock()
        args.fork = None  # All forks
        args.keep = 3
        args.dry_run = False

        extract_dir = Path("/tmp/test")

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        captured = capsys.readouterr()
        assert "No unmanaged releases to prune" in captured.out
        assert "Success" in captured.out

    def test_prune_with_dry_run(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test pruning with --dry-run flag (no confirmation required)."""
        mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
        mock_forgejo_fetcher = mocker.MagicMock(spec=ForgejoReleaseFetcher)
        # Simulate 2 versions to prune for CachyOS
        mock_fetcher.prune_releases.side_effect = [
            (["v3", "v2", "v1"], ["v0", "v-1"]),  # GE-Proton
            (["v3", "v2", "v1"], []),  # Proton-EM
            (["v3", "v2", "v1"], ["v0", "v-1"]),  # CachyOS
        ]
        mock_forgejo_fetcher.prune_releases.return_value = (["v3", "v2", "v1"], [])

        args = mocker.MagicMock()
        args.fork = None  # All forks
        args.keep = 3
        args.dry_run = True

        extract_dir = Path("/tmp/test")

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        captured = capsys.readouterr()
        assert "Would prune 4 old version(s)" in captured.out
        assert "Dry run complete - no changes made" in captured.out
        assert "Success" in captured.out
        # Should not ask for confirmation in dry-run mode
        assert "Proceed with pruning" not in captured.out

    def test_prune_single_fork(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test pruning a single fork."""
        mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
        mock_forgejo_fetcher = mocker.MagicMock(spec=ForgejoReleaseFetcher)
        mock_fetcher.prune_releases.return_value = (
            ["v3", "v2", "v1"],
            ["v0", "v-1"],
        )

        args = mocker.MagicMock()
        args.fork = "Proton-EM"  # Specific fork
        args.keep = 3
        args.dry_run = True

        extract_dir = Path("/tmp/test")

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        # Should only call prune_releases once for Proton-EM
        assert mock_fetcher.prune_releases.call_count == 1
        mock_fetcher.prune_releases.assert_called_with(
            extract_dir, ForkName.PROTON_EM, keep=3, dry_run=True
        )

    def test_prune_all_forks(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test pruning all forks (default behavior)."""
        mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
        mock_forgejo_fetcher = mocker.MagicMock(spec=ForgejoReleaseFetcher)
        mock_fetcher.prune_releases.return_value = (["v3", "v2", "v1"], [])
        mock_forgejo_fetcher.prune_releases.return_value = (["v3", "v2", "v1"], [])

        args = mocker.MagicMock()
        args.fork = None  # All forks
        args.keep = 3
        args.dry_run = True

        extract_dir = Path("/tmp/test")

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        # Should call prune_releases for all 4 forks
        assert mock_fetcher.prune_releases.call_count == 3
        calls = mock_fetcher.prune_releases.call_args_list
        assert calls[0][0][1] == ForkName.GE_PROTON
        assert calls[1][0][1] == ForkName.PROTON_EM
        assert calls[2][0][1] == ForkName.CACHYOS
        assert mock_forgejo_fetcher.prune_releases.call_count == 1
        assert mock_forgejo_fetcher.prune_releases.call_args[0][1] == ForkName.DW_PROTON

    def test_prune_with_confirmation_yes(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test pruning with user confirmation (yes)."""
        mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
        mock_forgejo_fetcher = mocker.MagicMock(spec=ForgejoReleaseFetcher)
        # Only GE-Proton has versions to prune
        mock_fetcher.prune_releases.side_effect = [
            (["v3", "v2", "v1"], ["v0"]),  # GE-Proton dry run
            (["v3", "v2", "v1"], []),  # Proton-EM dry run
            (["v3", "v2", "v1"], []),  # CachyOS dry run
            (["v3", "v2", "v1"], ["v0"]),  # GE-Proton actual prune
        ]
        mock_forgejo_fetcher.prune_releases.side_effect = [
            (["v3", "v2", "v1"], []),  # DW-Proton dry run
            (["v3", "v2", "v1"], []),  # DW-Proton actual prune
        ]

        args = mocker.MagicMock()
        args.fork = None
        args.keep = 3
        args.dry_run = False

        extract_dir = Path("/tmp/test")

        # Mock user input to confirm
        mocker.patch("builtins.input", return_value="y")

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        captured = capsys.readouterr()
        # The output shows what would be pruned and the result
        assert "Would prune 1 old version(s)" in captured.out
        assert "WARNING" in captured.out
        assert "Pruned 1 release(s)" in captured.out
        assert "Success" in captured.out

    def test_prune_with_confirmation_no(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test pruning with user declining (no)."""
        mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
        mock_forgejo_fetcher = mocker.MagicMock(spec=ForgejoReleaseFetcher)
        # Only GE-Proton has versions to prune
        mock_fetcher.prune_releases.side_effect = [
            (["v3", "v2", "v1"], ["v0"]),  # GE-Proton dry run
            (["v3", "v2", "v1"], []),  # Proton-EM dry run
            (["v3", "v2", "v1"], []),  # CachyOS dry run
        ]
        mock_forgejo_fetcher.prune_releases.return_value = (["v3", "v2", "v1"], [])

        args = mocker.MagicMock()
        args.fork = None
        args.keep = 3
        args.dry_run = False

        extract_dir = Path("/tmp/test")

        # Mock user input to decline
        mocker.patch("builtins.input", return_value="n")

        with pytest.raises(SystemExit) as exc_info:
            handle_prune_operation(
                mock_fetcher, mock_forgejo_fetcher, args, extract_dir
            )

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Aborted" in captured.out

    def test_prune_warning_message(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that pruning shows warning about prefix breakage."""
        mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
        mock_forgejo_fetcher = mocker.MagicMock(spec=ForgejoReleaseFetcher)
        # Only GE-Proton has versions to prune
        mock_fetcher.prune_releases.side_effect = [
            (["v3", "v2", "v1"], ["v0"]),  # GE-Proton dry run
            (["v3", "v2", "v1"], []),  # Proton-EM dry run
            (["v3", "v2", "v1"], []),  # CachyOS dry run
            (["v3", "v2", "v1"], ["v0"]),  # GE-Proton actual prune
        ]
        mock_forgejo_fetcher.prune_releases.side_effect = [
            (["v3", "v2", "v1"], []),  # DW-Proton dry run
            (["v3", "v2", "v1"], []),  # DW-Proton actual prune
        ]

        args = mocker.MagicMock()
        args.fork = None
        args.keep = 3
        args.dry_run = False

        extract_dir = Path("/tmp/test")

        mocker.patch("builtins.input", return_value="y")

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "Steam prefixes" in captured.out

    def test_prune_with_custom_keep(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test pruning with custom --keep value."""
        mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
        mock_forgejo_fetcher = mocker.MagicMock(spec=ForgejoReleaseFetcher)
        mock_fetcher.prune_releases.return_value = (["v5", "v4", "v3", "v2", "v1"], [])
        mock_forgejo_fetcher.prune_releases.return_value = (
            ["v5", "v4", "v3", "v2", "v1"],
            [],
        )

        args = mocker.MagicMock()
        args.fork = None
        args.keep = 5  # Keep 5 versions
        args.dry_run = True

        extract_dir = Path("/tmp/test")

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        # Verify keep=5 was passed to prune_releases
        for call in mock_fetcher.prune_releases.call_args_list:
            assert call[1]["keep"] == 5
        for call in mock_forgejo_fetcher.prune_releases.call_args_list:
            assert call[1]["keep"] == 5


# =============================================================================
# LinkManager Integration Tests
# =============================================================================


class TestLinkManagerPruneIntegration:
    """Integration tests for LinkManager.prune_releases()."""

    def test_prune_releases_prunes_linked_versions(
        self,
        link_manager: Any,
        mock_filesystem_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test that prune_releases does NOT protect linked versions."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create 5 GE-Proton version directories (correct format: GE-Proton10-X)
        # Higher number = newer version
        versions = []
        for i in range(5, 0, -1):
            v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()
            versions.append(v)

        # Use real filesystem client for symlink operations
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.link_manager import LinkManager

        fs = FileSystemClient()
        real_link_manager = LinkManager(fs)

        # Create symlink pointing to GE-Proton10-2 (older, outside top 3)
        # This version is now pruned (symlinks are no longer protected)
        main_link = extract_dir / "GE-Proton"
        main_link.symlink_to(versions[3])  # GE-Proton10-2

        # Act
        kept, pruned = real_link_manager.prune_releases(
            extract_dir, ForkName.GE_PROTON, keep=3, dry_run=True
        )

        # Assert
        # Top 3 newest (GE-Proton10-5, GE-Proton10-4, GE-Proton10-3) should be kept
        assert len(kept) == 3
        assert "GE-Proton10-5" in kept
        assert "GE-Proton10-4" in kept
        assert "GE-Proton10-3" in kept

        # GE-Proton10-2 IS now pruned (symlinks are no longer protected)
        assert "GE-Proton10-2" in pruned
        assert "GE-Proton10-1" in pruned

    def test_prune_releases_dry_run_no_deletion(
        self,
        link_manager: Any,
        mock_filesystem_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test that dry_run=True doesn't delete anything."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create 5 GE-Proton version directories (correct format: GE-Proton10-X)
        for i in range(5, 0, -1):
            v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()

        # Use real filesystem client
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.link_manager import LinkManager

        fs = FileSystemClient()
        real_link_manager = LinkManager(fs)

        # Act
        kept, pruned = real_link_manager.prune_releases(
            extract_dir, ForkName.GE_PROTON, keep=3, dry_run=True
        )

        # Assert
        assert len(pruned) == 2  # GE-Proton10-4, GE-Proton10-5 would be pruned
        # All directories should still exist
        for i in range(1, 6):
            assert (extract_dir / f"GE-Proton10-{i}").exists()

    def test_prune_releases_empty_directory(
        self,
        link_manager: Any,
        mock_filesystem_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test pruning when no versions exist."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Use real filesystem client
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.link_manager import LinkManager

        fs = FileSystemClient()
        real_link_manager = LinkManager(fs)

        # Act
        kept, pruned = real_link_manager.prune_releases(
            extract_dir, ForkName.GE_PROTON, keep=3, dry_run=True
        )

        # Assert
        assert kept == []
        assert pruned == []

    def test_prune_releases_keep_one(
        self,
        link_manager: Any,
        mock_filesystem_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test pruning with keep=1."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create 3 GE-Proton version directories (correct format: GE-Proton10-X)
        for i in range(3, 0, -1):
            v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()

        # Use real filesystem client
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.link_manager import LinkManager

        fs = FileSystemClient()
        real_link_manager = LinkManager(fs)

        # Act
        kept, pruned = real_link_manager.prune_releases(
            extract_dir, ForkName.GE_PROTON, keep=1, dry_run=True
        )

        # Assert
        assert len(kept) == 1  # Only newest
        assert len(pruned) == 2  # GE-Proton10-2, GE-Proton10-3 pruned

    def test_prune_releases_invalid_keep(
        self,
        link_manager: Any,
        mock_filesystem_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test pruning with invalid keep value."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Use real filesystem client
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.link_manager import LinkManager

        fs = FileSystemClient()
        real_link_manager = LinkManager(fs)

        # Act & Assert
        with pytest.raises(ValueError, match="keep must be at least 1"):
            real_link_manager.prune_releases(
                extract_dir, ForkName.GE_PROTON, keep=0, dry_run=True
            )

    def test_prune_releases_proton_em(
        self,
        link_manager: Any,
        mock_filesystem_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test pruning Proton-EM versions."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create Proton-EM version directories (correct format: proton-EM-10.0-X)
        for i in range(5, 0, -1):
            v = extract_dir / f"proton-EM-10.0-{i}"
            v.mkdir()

        # Use real filesystem client
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.link_manager import LinkManager

        fs = FileSystemClient()
        real_link_manager = LinkManager(fs)

        # Act
        kept, pruned = real_link_manager.prune_releases(
            extract_dir, ForkName.PROTON_EM, keep=3, dry_run=True
        )

        # Assert
        assert len(kept) == 3
        assert len(pruned) == 2

    def test_prune_releases_cachyos(
        self,
        link_manager: Any,
        mock_filesystem_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test pruning CachyOS versions."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create CachyOS version directories (correct format: proton-cachyos-10.0-YYYYMMDD-slr-x86_64)
        dates = ["20260321", "20260320", "20260228", "20260227", "20260207"]
        for date in dates:
            v = extract_dir / f"proton-cachyos-10.0-{date}-slr-x86_64"
            v.mkdir()

        # Use real filesystem client
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.link_manager import LinkManager

        fs = FileSystemClient()
        real_link_manager = LinkManager(fs)

        # Act
        kept, pruned = real_link_manager.prune_releases(
            extract_dir, ForkName.CACHYOS, keep=3, dry_run=True
        )

        # Assert
        assert len(kept) == 3
        assert len(pruned) == 2
        # Newest 3 should be kept
        assert any("20260321" in p for p in kept)
        assert any("20260320" in p for p in kept)
        assert any("20260228" in p for p in kept)


# =============================================================================
# End-to-End Prune Tests
# =============================================================================


class TestPruneE2E:
    """End-to-end tests for prune functionality."""

    def test_prune_e2e_all_forks_no_prunable(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        """End-to-end test: prune all forks with nothing to prune."""
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.link_manager import LinkManager

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create exactly 3 versions for each fork (nothing to prune)
        # GE-Proton format: GE-Proton10-X
        for i in range(3, 0, -1):
            (extract_dir / f"GE-Proton10-{i}").mkdir()
        # Proton-EM format: proton-EM-10.0-X
        for i in range(3, 0, -1):
            (extract_dir / f"proton-EM-10.0-{i}").mkdir()
        # CachyOS format: proton-cachyos-10.0-YYYYMMDD-slr-x86_64
        dates = ["20260321", "20260320", "20260228"]
        for date in dates:
            (extract_dir / f"proton-cachyos-10.0-{date}-slr-x86_64").mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)
        mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
        mock_forgejo_fetcher = mocker.MagicMock(spec=ForgejoReleaseFetcher)
        mock_fetcher.prune_releases = link_manager.prune_releases
        mock_forgejo_fetcher.prune_releases = link_manager.prune_releases

        args = mocker.MagicMock()
        args.fork = None
        args.keep = 3
        args.dry_run = True

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        captured = capsys.readouterr()
        assert "No unmanaged releases to prune" in captured.out

    def test_prune_e2e_with_prunable_versions(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        """End-to-end test: prune with versions to remove."""
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.link_manager import LinkManager

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create 5 GE-Proton versions (2 should be pruned: oldest ones)
        for i in range(5, 0, -1):
            (extract_dir / f"GE-Proton10-{i}").mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)
        mock_fetcher = mocker.MagicMock(spec=GitHubReleaseFetcher)
        mock_forgejo_fetcher = mocker.MagicMock(spec=ForgejoReleaseFetcher)
        mock_fetcher.prune_releases = link_manager.prune_releases
        mock_forgejo_fetcher.prune_releases = link_manager.prune_releases

        args = mocker.MagicMock()
        args.fork = "GE-Proton"
        args.keep = 3
        args.dry_run = True

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        captured = capsys.readouterr()
        assert "Would prune 2 old version(s)" in captured.out
        # The oldest 2 should be pruned
        assert "GE-Proton10-2" in captured.out
        assert "GE-Proton10-1" in captured.out
