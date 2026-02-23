"""
Check mode tests for ProtonFetcher.

Tests for the --check/-c flag that provides script-friendly update checking.
"""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.cli import _handle_check_operation_flow, main
from protonfetcher.common import ForkName
from protonfetcher.github_fetcher import GitHubReleaseFetcher
from protonfetcher.link_manager import LinkManager
from protonfetcher.release_manager import ReleaseManager


class TestCheckForNewerRelease:
    """Tests for ReleaseManager.check_for_newer_release() method."""

    def test_newer_release_available(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test detection when a newer release is available."""

        # Mock network to return latest tag GE-Proton10-21
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Current version is older (GE-Proton10-20)
        result = release_manager.check_for_newer_release(
            "GloriousEggroll/proton-ge-custom",
            ["GE-Proton10-20"],
            ForkName.GE_PROTON,
        )

        assert result == "GE-Proton10-21"

    def test_already_up_to_date(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test when already on latest version."""

        # Mock network to return latest tag GE-Proton10-20 (same as current)
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-20"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-20",
            stderr="",
        )

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        result = release_manager.check_for_newer_release(
            "GloriousEggroll/proton-ge-custom",
            ["GE-Proton10-20"],
            ForkName.GE_PROTON,
        )

        assert result is None

    def test_no_installed_versions(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test when no versions are installed (should return latest)."""

        # Mock network to return latest tag
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        result = release_manager.check_for_newer_release(
            "GloriousEggroll/proton-ge-custom",
            [],
            ForkName.GE_PROTON,
        )

        assert result == "GE-Proton10-21"

    def test_multiple_current_versions(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test comparison with multiple installed versions."""

        # Mock network to return latest tag GE-Proton10-22
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-22"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-22",
            stderr="",
        )

        release_manager = ReleaseManager(mock_network_client, mock_filesystem_client)

        # Multiple current versions, newest is GE-Proton10-20
        result = release_manager.check_for_newer_release(
            "GloriousEggroll/proton-ge-custom",
            ["GE-Proton10-18", "GE-Proton10-19", "GE-Proton10-20"],
            ForkName.GE_PROTON,
        )

        assert result == "GE-Proton10-22"


class TestGetInstalledVersions:
    """Tests for LinkManager.get_installed_versions() method."""

    def test_get_installed_versions_newest_first(
        self,
        tmp_path: Path,
        mocker: Any,
        fork: ForkName,
    ) -> None:
        """Test that versions are returned sorted newest first."""
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create version directories based on fork type
        if fork == ForkName.GE_PROTON:
            versions = ["GE-Proton10-18", "GE-Proton10-20", "GE-Proton10-19"]
        elif fork == ForkName.PROTON_EM:
            versions = ["EM-10.0-28", "EM-10.0-30", "EM-10.0-29"]
        else:  # CACHYOS
            versions = [
                "cachyos-10.0-20260207-slr",
                "cachyos-10.0-20260215-slr",
                "cachyos-10.0-20260210-slr",
            ]

        for version in versions:
            (extract_dir / version).mkdir()

        fs = FileSystemClient()
        lm = LinkManager(fs)

        result = lm.get_installed_versions(extract_dir, fork)

        # Should be sorted newest first
        assert len(result) == 3
        if fork == ForkName.GE_PROTON:
            assert result[0] == "GE-Proton10-20"
            assert result[1] == "GE-Proton10-19"
            assert result[2] == "GE-Proton10-18"
        elif fork == ForkName.PROTON_EM:
            assert result[0] == "EM-10.0-30"
            assert result[1] == "EM-10.0-29"
            assert result[2] == "EM-10.0-28"
        else:  # CACHYOS
            # CachyOS versions are sorted by date
            assert result[0] == "cachyos-10.0-20260215-slr"
            assert result[1] == "cachyos-10.0-20260210-slr"
            assert result[2] == "cachyos-10.0-20260207-slr"

    def test_get_installed_versions_empty(
        self,
        tmp_path: Path,
        mocker: Any,
        fork: ForkName,
    ) -> None:
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

    def test_check_for_updates_available(
        self,
        mocker: Any,
        mock_network_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test check_for_updates when update is available."""
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create an older version directory
        (extract_dir / "GE-Proton10-20").mkdir()

        # Mock network to return newer latest tag
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )

        # Use real filesystem client to properly find installed versions
        fs = FileSystemClient()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=fs,
        )

        result = fetcher.check_for_updates(extract_dir, ForkName.GE_PROTON)

        assert result == "GE-Proton10-21"

    def test_check_for_updates_up_to_date(
        self,
        mocker: Any,
        mock_network_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test check_for_updates when already up-to-date."""
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create latest version directory
        (extract_dir / "GE-Proton10-21").mkdir()

        # Mock network to return same latest tag
        # Note: fetch_latest_tag uses head, check_for_newer_release uses get
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )

        # Use real filesystem client to properly find installed versions
        fs = FileSystemClient()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=fs,
        )

        result = fetcher.check_for_updates(extract_dir, ForkName.GE_PROTON)

        # When versions are equal, no update is available
        assert result is None


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
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create older version
        (extract_dir / "GE-Proton10-20").mkdir()

        # Mock network for newer release
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

        # Create mock args
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
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create latest version
        (extract_dir / "GE-Proton10-21").mkdir()

        # Mock network for same latest release
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )

        # Use real filesystem client to properly find installed versions
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
        assert "GE-Proton: up-to-date" in captured.out  # Shows up-to-date status

    def test_check_all_managed_forks(
        self,
        mocker: Any,
        mock_network_client: Any,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test check operation for all managed forks."""
        from protonfetcher.filesystem import FileSystemClient
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create GE-Proton version (older)
        (extract_dir / "GE-Proton10-20").mkdir()

        # Create symlinks for GE-Proton to make it "managed"
        fs = FileSystemClient()
        lm = LinkManager(fs)
        lm.create_symlinks_for_test(
            extract_dir, extract_dir / "GE-Proton10-20", ForkName.GE_PROTON
        )

        # Mock network for newer GE-Proton release
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )

        # Use real filesystem client for link_manager
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=fs,
        )

        args = mocker.MagicMock()
        args.fork = None  # -f without value
        args.check = True

        exit_code = _handle_check_operation_flow(fetcher, args, extract_dir)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "New release available for GE-Proton: GE-Proton10-21!" in captured.out


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

        # Create GE-Proton version (older)
        (extract_dir / "GE-Proton10-20").mkdir()

        # Create symlinks for GE-Proton to make it "managed"
        fs = FileSystemClient()
        lm = LinkManager(fs)
        lm.create_symlinks_for_test(
            extract_dir, extract_dir / "GE-Proton10-20", ForkName.GE_PROTON
        )

        # Mock network for newer GE-Proton release
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "GE-Proton10-21"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )

        # Pass custom extract_dir
        mocker.patch(
            "sys.argv",
            ["protonfetcher", "--check", "-x", str(extract_dir)],
        )

        # Mock the fetcher to use our mocks
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

        # Exit code 0 means updates available
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "New release available for GE-Proton: GE-Proton10-21!" in captured.out

    def test_check_mutually_exclusive_with_dry_run(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that --check cannot be used with --dry-run."""
        mocker.patch(
            "sys.argv",
            ["protonfetcher", "--fork", "GE-Proton", "--check", "--dry-run"],
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--check cannot be used with" in captured.out

    def test_check_mutually_exclusive_with_list(
        self,
        mocker: Any,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that --check cannot be used with --list."""
        mocker.patch(
            "sys.argv",
            ["protonfetcher", "--fork", "GE-Proton", "--check", "--list"],
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--check cannot be used with" in captured.out

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

        # Create older version
        (extract_dir / "GE-Proton10-20").mkdir()

        # Mock network for newer release
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

        # Use real filesystem client
        fs = FileSystemClient()

        # Mock the fetcher to use our mocks
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

        # Exit code 0 means updates available
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "New release available for GE-Proton: GE-Proton10-21!" in captured.out
