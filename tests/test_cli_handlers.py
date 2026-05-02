"""Tests for CLI handler functions.

Tests for handle_check_operation(), handle_ls_operation(), and other
handler functions in protonfetcher.cli.handlers.
"""

import argparse
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from protonfetcher.cli.handlers import (
    handle_check_operation,
    handle_list_operation,
    handle_ls_operation,
    handle_prune_operation,
    handle_relink_operation,
    handle_rm_operation,
)
from protonfetcher.github_fetcher import GitHubReleaseFetcher

# =============================================================================
# handle_check_operation Tests
# =============================================================================


class TestHandleCheckOperation:
    """Tests for handle_check_operation()."""

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

        args = MagicMock()
        args.fork = "GE-Proton"
        args.check = True

        forgejo_fetcher = MagicMock()

        with pytest.raises(SystemExit) as exc_info:
            handle_check_operation(fetcher, forgejo_fetcher, args, extract_dir)
        assert exc_info.value.code == 0

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

        args = MagicMock()
        args.fork = "GE-Proton"
        args.check = True

        forgejo_fetcher = MagicMock()

        with pytest.raises(SystemExit) as exc_info:
            handle_check_operation(fetcher, forgejo_fetcher, args, extract_dir)
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "GE-Proton: up-to-date" in captured.out


# =============================================================================
# handle_ls_operation Tests
# =============================================================================


class TestHandleLsOperation:
    """Tests for handle_ls_operation()."""

    def test_ls_shows_links_for_all_forks(
        self,
        mocker: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test --ls shows links for all forks."""
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create some fake links
        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()
        (version_dir / "version").write_text("GE-Proton10-20")

        fs = FileSystemClient()
        link_path = extract_dir / "GE-Proton"
        fs.symlink_to(link_path, version_dir, target_is_directory=True)

        mock_fetcher = MagicMock()
        mock_forgejo_fetcher = MagicMock()

        args = argparse.Namespace(ls=True, fork=None)

        handle_ls_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        captured = capsys.readouterr()
        assert "Links for GE-Proton" in captured.out

    def test_ls_with_fork_filter(
        self,
        mocker: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test --ls with --fork shows only that fork."""
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()
        (version_dir / "version").write_text("GE-Proton10-20")

        fs = FileSystemClient()
        link_path = extract_dir / "GE-Proton"
        fs.symlink_to(link_path, version_dir, target_is_directory=True)

        mock_fetcher = MagicMock()
        mock_forgejo_fetcher = MagicMock()

        args = argparse.Namespace(ls=True, fork="GE-Proton")

        handle_ls_operation(mock_fetcher, mock_forgejo_fetcher, args, extract_dir)

        captured = capsys.readouterr()
        assert "Links for GE-Proton" in captured.out


# =============================================================================
# handle_list_operation Tests
# =============================================================================


class TestHandleListOperation:
    """Tests for handle_list_operation()."""

    def test_list_shows_recent_releases(
        self,
        mocker: Any,
        mock_network_client: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test --list shows recent releases."""
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"assets": [{"name": "GE-Proton10-20.tar.gz", "size": 1048576}]}',
            stderr="",
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-20",
            stderr="",
        )

        from protonfetcher.filesystem import FileSystemClient

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=FileSystemClient(),
        )
        forgejo_fetcher = MagicMock()

        args = MagicMock()
        args.fork = "GE-Proton"

        handle_list_operation(fetcher, forgejo_fetcher, args, tmp_path)

        captured = capsys.readouterr()
        assert "Recent releases:" in captured.out


# =============================================================================
# handle_relink_operation Tests
# =============================================================================


class TestHandleRelinkOperation:
    """Tests for handle_relink_operation()."""

    def test_relink_calls_fork_fetcher(
        self,
        mocker: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test --relink calls relink_fork on the appropriate fetcher."""
        mock_fetcher = MagicMock()
        mock_forgejo_fetcher = MagicMock()

        args = MagicMock()
        args.fork = "GE-Proton"

        handle_relink_operation(mock_fetcher, mock_forgejo_fetcher, args, tmp_path)

        mock_fetcher.relink_fork.assert_called_once()
        captured = capsys.readouterr()
        assert "Success" in captured.out


# =============================================================================
# handle_rm_operation Tests
# =============================================================================


class TestHandleRmOperation:
    """Tests for handle_rm_operation()."""

    def test_rm_calls_remove_release(
        self,
        mocker: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test --rm calls remove_release on the appropriate fetcher."""
        mock_fetcher = MagicMock()
        mock_forgejo_fetcher = MagicMock()

        args = MagicMock()
        args.fork = "GE-Proton"
        args.rm = "GE-Proton10-20"

        handle_rm_operation(mock_fetcher, mock_forgejo_fetcher, args, tmp_path)

        mock_fetcher.link_manager.remove_release.assert_called_once()
        captured = capsys.readouterr()
        assert "Success" in captured.out

    def test_rm_with_fork_removes_all_symlinks(
        self,
        mocker: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test --rm --fork removes all symlinks for that fork."""
        mock_fetcher = MagicMock()
        mock_forgejo_fetcher = MagicMock()

        args = MagicMock()
        args.fork = "CachyOS"
        args.rm = None  # No tag, just fork

        handle_rm_operation(mock_fetcher, mock_forgejo_fetcher, args, tmp_path)

        # Should NOT call remove_release (no tag)
        mock_fetcher.link_manager.remove_release.assert_not_called()
        captured = capsys.readouterr()
        assert "Removed all symlinks for CachyOS" in captured.out
        assert "Success" in captured.out

    def test_rm_with_tag_removes_release(
        self,
        mocker: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test --rm <tag> removes the specific release."""
        mock_fetcher = MagicMock()
        mock_forgejo_fetcher = MagicMock()

        args = MagicMock()
        args.fork = "GE-Proton"
        args.rm = "GE-Proton10-15"

        handle_rm_operation(mock_fetcher, mock_forgejo_fetcher, args, tmp_path)

        mock_fetcher.link_manager.remove_release.assert_called_once_with(
            tmp_path, "GE-Proton10-15", mocker.ANY
        )
        captured = capsys.readouterr()
        assert "Removed GE-Proton10-15" in captured.out


# =============================================================================
# handle_prune_operation Tests
# =============================================================================


class TestHandlePruneOperation:
    """Tests for handle_prune_operation()."""

    def test_prune_single_fork(
        self,
        mocker: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test --prune with --fork prunes only that fork."""
        mock_fetcher = MagicMock()
        mock_forgejo_fetcher = MagicMock()
        mock_fetcher.prune_releases.return_value = ([], [])
        mock_forgejo_fetcher.prune_releases.return_value = ([], [])

        args = argparse.Namespace(fork="GE-Proton", keep=3)

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, tmp_path)

        mock_fetcher.prune_releases.assert_called_once()
        captured = capsys.readouterr()
        assert "Success" in captured.out

    def test_prune_all_forks(
        self,
        mocker: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test --prune without --fork prunes all forks."""
        mock_fetcher = MagicMock()
        mock_forgejo_fetcher = MagicMock()
        mock_fetcher.prune_releases.return_value = ([], [])
        mock_forgejo_fetcher.prune_releases.return_value = ([], [])

        args = argparse.Namespace(fork=None, keep=3)

        handle_prune_operation(mock_fetcher, mock_forgejo_fetcher, args, tmp_path)

        # Should be called for each fork
        assert mock_fetcher.prune_releases.call_count >= 1
        captured = capsys.readouterr()
        assert "Success" in captured.out
