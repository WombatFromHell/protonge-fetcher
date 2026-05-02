"""
Unit tests for GitHubReleaseFetcher orchestrator.

GitHubReleaseFetcher is a marker class (~10 lines, zero method overrides)
that delegates all behavior to BaseReleaseFetcher + GitHubPlatformAdapter.

Tests in this file verify:
- Error handling scenarios (curl missing, asset not found, etc.)
- Skip logic for existing directories
- Multi-fork update logic

Adapter selection is tested in test_base_release_fetcher.py.
Complete workflow tests are in test_cli.py to avoid duplication.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import (
    LinkManagementError,
    NetworkError,
    ProtonFetcherError,
)
from protonfetcher.github_fetcher import GitHubReleaseFetcher

# =============================================================================
# Fetch and Extract - Error Handling & Edge Cases
# =============================================================================


class TestFetchAndExtractEdgeCases:
    """Test fetch_and_extract error handling and edge cases."""

    def test_fetch_and_extract_skip_existing_directory_mocked(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test that existing directories are skipped (mocked)."""
        tag = "GE-Proton10-20"
        output_dir = Path("/mock/Downloads")
        extract_dir = Path("/mock/compatibilitytools.d")
        existing_dir = extract_dir / tag

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
            timeout=30,
        )

        # Patch Path.exists/is_dir for _check_existing_directory (uses Path directly)
        mocker.patch(
            "protonfetcher.base_release_fetcher.Path.exists",
            return_value=True,
        )
        mocker.patch(
            "protonfetcher.base_release_fetcher.Path.is_dir",
            return_value=True,
        )

        # Mock the fetcher's file_system_client for _ensure_directory_is_writable
        mocker.patch.object(
            fetcher.file_system_client,
            "exists",
            return_value=True,
        )
        mocker.patch.object(
            fetcher.file_system_client,
            "is_dir",
            return_value=True,
        )
        mocker.patch.object(
            fetcher.file_system_client,
            "mkdir",
            return_value=None,
        )
        mocker.patch.object(
            fetcher.file_system_client,
            "write",
            return_value=None,
        )
        mocker.patch.object(
            fetcher.file_system_client,
            "unlink",
            return_value=None,
        )

        # Mock the release_manager's file_system_client for directory checks
        mocker.patch.object(
            fetcher.release_manager.file_system_client,
            "exists",
            return_value=True,
        )
        mocker.patch.object(
            fetcher.release_manager.file_system_client,
            "is_dir",
            return_value=True,
        )

        result_path = fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=output_dir,
            extract_dir=extract_dir,
            release_tag=tag,
            fork=ForkName.GE_PROTON,
            show_progress=False,
            show_file_details=False,
        )

        assert result_path == existing_dir
        mock_network_client.get.assert_not_called()
        mock_network_client.download.assert_not_called()

    def test_fetch_and_extract_asset_not_found_mocked(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test handling when asset is not found (mocked)."""
        output_dir = Path("/mock/Downloads")
        extract_dir = Path("/mock/compatibilitytools.d")

        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"assets": [{"name": "different.tar.gz", "size": 1024}]}),
            stderr="",
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-20",
            stderr="",
        )

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
            timeout=30,
        )

        # Mock cache to avoid mock filesystem mtime issues
        mocker.patch.object(
            fetcher.release_manager, "_get_cached_asset_size", return_value=None
        )

        # Asset is found but get_remote_asset_size fails (mock doesn't have proper HEAD)
        with pytest.raises(NetworkError, match="Failed to get remote asset size"):
            fetcher.fetch_and_extract(
                repo="GloriousEggroll/proton-ge-custom",
                output_dir=output_dir,
                extract_dir=extract_dir,
                fork=ForkName.GE_PROTON,
                show_progress=False,
                show_file_details=False,
            )

    def test_fetch_and_extract_curl_not_available_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test handling when curl is not available."""
        mocker.patch("shutil.which", return_value=None)

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        with pytest.raises(ProtonFetcherError, match="curl is not available"):
            fetcher.fetch_and_extract(
                repo="GloriousEggroll/proton-ge-custom",
                output_dir=Path("/mock/Downloads"),
                extract_dir=Path("/mock/extract"),
                fork=ForkName.GE_PROTON,
            )


# =============================================================================
# Remove Release - Error Handling
# =============================================================================


class TestRemoveRelease:
    """Test remove_release error handling."""

    def test_remove_nonexistent_release_mocked(
        self,
        mocker: Any,
        mock_filesystem_factory: Any,
    ) -> None:
        """Test removing non-existent release raises error (mocked)."""
        mock_filesystem_client = mock_filesystem_factory()
        mock_filesystem_client.exists.side_effect = lambda p: False

        extract_dir = Path("/mock/compatibilitytools.d")

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        with pytest.raises(LinkManagementError):
            fetcher.remove_release(extract_dir, "NonExistent-10-20", ForkName.GE_PROTON)


# =============================================================================
# Relink Fork - Error Handling
# =============================================================================


class TestRelinkFork:
    """Test relink_fork error handling."""

    def test_relink_fork_no_versions_raises_error_mocked(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
    ) -> None:
        """Test relinking when no versions exist raises error."""
        extract_dir = Path("/mock/compatibilitytools.d")

        mock_filesystem_client.exists.return_value = True
        mock_filesystem_client.is_dir.return_value = True
        mock_filesystem_client.iterdir.return_value = iter([])

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        with pytest.raises(LinkManagementError, match="No.*Proton.*found"):
            fetcher.relink_fork(extract_dir, ForkName.GE_PROTON)


# =============================================================================
# Multi-Fork Update Tests
# =============================================================================


class TestUpdateAllManagedForks:
    """Test update_all_managed_forks workflow."""

    def test_update_all_managed_forks_updates_forks_with_links(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mock_tarfile_operations: Any,
        temp_environment: dict[str, Path],
    ) -> None:
        """Test that update_all_managed_forks updates forks with managed links."""
        extract_dir = temp_environment["extract_dir"]

        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {"assets": [{"name": "GE-Proton10-21.tar.gz", "size": 1024}]}
            ),
            stderr="",
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )
        mock_network_client.download.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        mock_tarfile_operations(
            members=[
                {"name": "GE-Proton10-21", "is_dir": True, "size": 0},
            ]
        )

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        result = fetcher.update_all_managed_forks(
            output_dir=temp_environment["output_dir"],
            extract_dir=extract_dir,
        )

        assert isinstance(result, dict)

    def test_update_all_managed_forks_dry_run(
        self,
        mocker: Any,
        mock_network_client: Any,
        temp_environment: dict[str, Path],
    ) -> None:
        """Test that update_all_managed_forks respects dry_run flag."""
        extract_dir = temp_environment["extract_dir"]

        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {"assets": [{"name": "GE-Proton10-21.tar.gz", "size": 1024}]}
            ),
            stderr="",
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/GE-Proton10-21",
            stderr="",
        )

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mocker.MagicMock(),
        )

        result = fetcher.update_all_managed_forks(
            output_dir=temp_environment["output_dir"],
            extract_dir=extract_dir,
            dry_run=True,
        )

        assert isinstance(result, dict)
        mock_network_client.download.assert_not_called()

    def test_update_all_managed_forks_no_managed_links(
        self,
        mocker: Any,
        mock_filesystem_client: Any,
        temp_environment: dict[str, Path],
    ) -> None:
        """Test update_all_managed_forks when no managed links exist."""
        extract_dir = temp_environment["extract_dir"]

        mock_filesystem_client.exists.return_value = True
        mock_filesystem_client.is_dir.return_value = True
        mock_filesystem_client.is_symlink.return_value = False
        mock_filesystem_client.iterdir.return_value = iter([])

        fetcher = GitHubReleaseFetcher(file_system_client=mock_filesystem_client)

        result = fetcher.update_all_managed_forks(
            output_dir=temp_environment["output_dir"],
            extract_dir=extract_dir,
        )

        assert result == {}

    def test_update_all_managed_forks_handles_errors_gracefully(
        self,
        mocker: Any,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        temp_environment: dict[str, Path],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that update_all_managed_forks handles errors gracefully."""
        extract_dir = temp_environment["extract_dir"]

        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        mock_network_client.get.side_effect = Exception("Network failed")

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=mock_filesystem_client,
        )

        result = fetcher.update_all_managed_forks(
            output_dir=temp_environment["output_dir"],
            extract_dir=extract_dir,
        )

        assert isinstance(result, dict)
        assert (
            "No managed forks" in caplog.text
            or "Error" in caplog.text
            or "Failed" in caplog.text
        )


# =============================================================================
# check_for_updates Tests (moved from test_cli.py)
# =============================================================================


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

    def test_check_with_special_build_suffix_installed(
        self,
        mocker: Any,
        mock_network_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test that check_for_updates correctly handles special build suffixes.

        This is a regression test for the bug where directories like proton-EM-10.0-36-HDRTEST
        were not recognized, causing --check to incorrectly report updates available when
        the latest version was already installed.
        """
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Install the HDRTEST version (special build suffix)
        (extract_dir / "proton-EM-10.0-36-HDRTEST").mkdir()

        # Mock the latest tag to be the same as the installed version
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "EM-10.0-36"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/EM-10.0-36",
            stderr="",
        )

        fs = FileSystemClient()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=fs,
        )

        # Should return None since we have 10.0.36 installed (HDRTEST is same version)
        result = fetcher.check_for_updates(extract_dir, ForkName.PROTON_EM)
        assert result is None

    def test_check_with_older_special_build_suffix(
        self,
        mocker: Any,
        mock_network_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test that check_for_updates reports update when newer version available.

        When an older special build suffix version is installed, check should
        correctly report that a newer version is available.
        """
        from protonfetcher.filesystem import FileSystemClient

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Install an older HDRTEST version
        (extract_dir / "proton-EM-10.0-33-HDRTEST").mkdir()

        # Mock the latest tag to be newer
        mock_network_client.get.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"tag_name": "EM-10.0-36"}', stderr=""
        )
        mock_network_client.head.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Location: /releases/tag/EM-10.0-36",
            stderr="",
        )

        fs = FileSystemClient()
        fetcher = GitHubReleaseFetcher(
            network_client=mock_network_client,
            file_system_client=fs,
        )

        # Should return the newer version
        result = fetcher.check_for_updates(extract_dir, ForkName.PROTON_EM)
        assert result == "EM-10.0-36"
