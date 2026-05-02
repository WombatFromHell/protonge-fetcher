"""Tests for BaseReleaseFetcher shared workflow methods."""

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import LinkManagementError, ProtonFetcherError
from protonfetcher.forgejo_fetcher import ForgejoReleaseFetcher
from protonfetcher.github_fetcher import GitHubReleaseFetcher


class TestBaseReleaseFetcherSharedWorkflow:
    """Tests that verify the shared workflow in BaseReleaseFetcher works correctly."""

    def test_fetch_and_extract_skips_existing_directory(
        self,
        mocker: Any,
        mock_network_factory: Any,
        mock_filesystem_factory: Any,
        tmp_path: Path,
    ) -> None:
        """Test that fetch_and_extract skips download when directory already exists."""
        mock_network = mock_network_factory()
        mock_fs = mock_filesystem_factory(use_tmp_path=True)

        # Create the extract and output directories
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        output_dir = tmp_path / "downloads"
        output_dir.mkdir()

        # Create the version directory at the correct path
        version_dir = extract_dir / "dwproton-10.0-26-x86_64"
        version_dir.mkdir()

        fetcher = ForgejoReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
        )

        result = fetcher.fetch_and_extract(
            repo="dawn-winery/dwproton",
            output_dir=output_dir,
            extract_dir=extract_dir,
            release_tag="dwproton-10.0-26",
            fork=ForkName.DW_PROTON,
            dry_run=False,
        )

        assert result == version_dir
        # Should not have called download since directory existed
        mock_network.download.assert_not_called()

    def test_relink_fork_success(
        self,
        tmp_path: Path,
    ) -> None:
        """Test relink_fork creates symlinks for existing versions."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create version directories
        v1 = extract_dir / "dwproton-10.0-26-x86_64"
        v2 = extract_dir / "dwproton-10.0-25-x86_64"
        v3 = extract_dir / "dwproton-10.0-24-x86_64"
        v1.mkdir()
        v2.mkdir()
        v3.mkdir()

        fetcher = ForgejoReleaseFetcher()
        result = fetcher.relink_fork(extract_dir, ForkName.DW_PROTON)

        assert result is True
        assert (extract_dir / "DW-Proton").is_symlink()
        assert (extract_dir / "DW-Proton-Fallback").is_symlink()
        assert (extract_dir / "DW-Proton-Fallback2").is_symlink()

    def test_relink_fork_no_versions_raises(
        self,
        tmp_path: Path,
    ) -> None:
        """Test relink_fork raises when no valid versions exist."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        fetcher = ForgejoReleaseFetcher()
        with pytest.raises(LinkManagementError, match="No valid DW-Proton versions"):
            fetcher.relink_fork(extract_dir, ForkName.DW_PROTON)

    def test_prune_releases_delegates_to_link_manager(
        self,
        mocker: Any,
        tmp_path: Path,
    ) -> None:
        """Test prune_releases delegates to LinkManager.prune_releases."""
        fetcher = ForgejoReleaseFetcher()
        mock_prune = mocker.patch.object(
            fetcher.link_manager, "prune_releases", return_value=(["v1"], ["v2"])
        )

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        kept, pruned = fetcher.prune_releases(
            extract_dir, ForkName.DW_PROTON, keep=3, dry_run=False
        )

        mock_prune.assert_called_once_with(extract_dir, ForkName.DW_PROTON, 3, False)
        assert kept == ["v1"]
        assert pruned == ["v2"]

    def test_list_links_delegates_to_link_manager(
        self,
        mocker: Any,
        tmp_path: Path,
    ) -> None:
        """Test list_links delegates to LinkManager.list_links."""
        fetcher = ForgejoReleaseFetcher()
        mock_list = mocker.patch.object(
            fetcher.link_manager,
            "list_links",
            return_value={"DW-Proton": "dwproton-10.0-26-x86_64"},
        )

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        result = fetcher.list_links(extract_dir, ForkName.DW_PROTON)

        mock_list.assert_called_once_with(extract_dir, ForkName.DW_PROTON)
        assert result == {"DW-Proton": "dwproton-10.0-26-x86_64"}

    def test_remove_release_delegates_to_link_manager(
        self,
        mocker: Any,
        tmp_path: Path,
    ) -> None:
        """Test remove_release delegates to LinkManager.remove_release."""
        fetcher = ForgejoReleaseFetcher()
        mock_remove = mocker.patch.object(
            fetcher.link_manager, "remove_release", return_value=True
        )

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        result = fetcher.remove_release(
            extract_dir, "dwproton-10.0-26", ForkName.DW_PROTON
        )

        mock_remove.assert_called_once_with(
            extract_dir, "dwproton-10.0-26", ForkName.DW_PROTON
        )
        assert result is True

    def test_ensure_directory_is_writable_creates_missing(
        self,
        mocker: Any,
        mock_filesystem_factory: Any,
        tmp_path: Path,
    ) -> None:
        """Test _ensure_directory_is_writable creates missing directories."""
        mock_fs = mock_filesystem_factory(use_tmp_path=True)
        fetcher = ForgejoReleaseFetcher(file_system_client=mock_fs)

        new_dir = tmp_path / "new" / "nested" / "dir"
        fetcher._ensure_directory_is_writable(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_ensure_directory_is_writable_raises_on_non_directory(
        self,
        mocker: Any,
        mock_filesystem_factory: Any,
        tmp_path: Path,
    ) -> None:
        """Test _ensure_directory_is_writable raises when path is a file."""
        mock_fs = mock_filesystem_factory(use_tmp_path=True)
        fetcher = ForgejoReleaseFetcher(file_system_client=mock_fs)

        # Create a file at the path
        file_path = tmp_path / "not_a_dir"
        file_path.write_bytes(b"content")

        with pytest.raises(ProtonFetcherError, match="exists but is not a directory"):
            fetcher._ensure_directory_is_writable(file_path)

    def test_dry_run_workflow_shows_download_info(
        self,
        mocker: Any,
        mock_network_factory: Any,
        tmp_path: Path,
    ) -> None:
        """Test _dry_run_workflow logs what would be downloaded."""
        mock_network = mock_network_factory()
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)

        # Mock find_asset_by_name and get_remote_asset_size
        mocker.patch.object(
            fetcher, "find_asset_by_name", return_value="dwproton-10.0-26-x86_64.tar.xz"
        )
        mocker.patch.object(fetcher, "get_remote_asset_size", return_value=281758252)

        extract_dir = tmp_path / "compatibilitytools.d"
        output_dir = tmp_path / "downloads"
        extract_dir.mkdir()
        output_dir.mkdir()

        result = fetcher._dry_run_workflow(
            repo="dawn-winery/dwproton",
            output_dir=output_dir,
            extract_dir=extract_dir,
            release_tag="dwproton-10.0-26",
            fork=ForkName.DW_PROTON,
            is_manual_release=True,
        )

        assert result is None

    def test_determine_release_tag_uses_latest_when_none(
        self,
        mocker: Any,
        mock_network_factory: Any,
    ) -> None:
        """Test _determine_release_tag calls fetch_latest_tag when tag is None."""
        mock_network = mock_network_factory()
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)

        mocker.patch.object(
            fetcher, "fetch_latest_tag", return_value="dwproton-10.0-26"
        )

        tag = fetcher._determine_release_tag("dawn-winery/dwproton", None)
        assert tag == "dwproton-10.0-26"

    def test_determine_release_tag_uses_manual_when_provided(
        self,
        mocker: Any,
        mock_network_factory: Any,
    ) -> None:
        """Test _determine_release_tag uses manual tag when provided."""
        mock_network = mock_network_factory()
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)

        tag = fetcher._determine_release_tag("dawn-winery/dwproton", "dwproton-9.0-25")
        assert tag == "dwproton-9.0-25"

    def test_determine_release_tag_prefers_manual_release_tag_kwarg(
        self,
        mocker: Any,
        mock_network_factory: Any,
    ) -> None:
        """Test _determine_release_tag prefers manual_release_tag kwarg."""
        mock_network = mock_network_factory()
        fetcher = ForgejoReleaseFetcher(network_client=mock_network)

        tag = fetcher._determine_release_tag(
            "dawn-winery/dwproton",
            None,
            manual_release_tag="dwproton-8.0-20",
        )
        assert tag == "dwproton-8.0-20"


# =============================================================================
# Adapter Selection Tests (Phase 2.1)
# =============================================================================


class TestAdapterSelection:
    """Tests verifying that the correct PlatformAdapter is selected per fetcher."""

    def test_github_fetcher_uses_github_adapter(
        self,
        mock_network_factory: Any,
        mock_filesystem_factory: Any,
    ) -> None:
        """Test GitHubReleaseFetcher gets github_adapter in its ReleaseManager."""
        from protonfetcher.platform_adapters import github_adapter

        mock_network = mock_network_factory()
        mock_fs = mock_filesystem_factory()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
        )

        assert fetcher.platform == "github"
        assert fetcher.release_manager.platform_adapter is github_adapter

    def test_forgejo_fetcher_uses_forgejo_adapter(
        self,
        mock_network_factory: Any,
        mock_filesystem_factory: Any,
    ) -> None:
        """Test ForgejoReleaseFetcher gets forgejo_adapter in its ReleaseManager."""
        from protonfetcher.platform_adapters import forgejo_adapter

        mock_network = mock_network_factory()
        mock_fs = mock_filesystem_factory()

        fetcher = ForgejoReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
        )

        assert fetcher.platform == "forgejo"
        assert fetcher.release_manager.platform_adapter is forgejo_adapter


# =============================================================================
# _build_download_url Tests (Phase 2.2)
# =============================================================================


class TestBuildDownloadUrl:
    """Tests verifying _build_download_url delegates to the platform adapter."""

    def test_github_fetcher_builds_github_download_url(
        self,
        mock_network_factory: Any,
        mock_filesystem_factory: Any,
    ) -> None:
        """Test GitHubReleaseFetcher builds GitHub-style download URL."""
        mock_network = mock_network_factory()
        mock_fs = mock_filesystem_factory()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
        )

        url = fetcher._build_download_url(
            "GloriousEggroll/proton-ge-custom",
            "GE-Proton10-20",
            "GE-Proton10-20.tar.gz",
        )

        assert (
            url
            == "https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton10-20/GE-Proton10-20.tar.gz"
        )

    def test_forgejo_fetcher_builds_forgejo_download_url(
        self,
        mock_network_factory: Any,
        mock_filesystem_factory: Any,
    ) -> None:
        """Test ForgejoReleaseFetcher builds Forgejo-style download URL."""
        mock_network = mock_network_factory()
        mock_fs = mock_filesystem_factory()

        fetcher = ForgejoReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
        )

        url = fetcher._build_download_url(
            "dawn-winery/dwproton",
            "dwproton-10.0-26",
            "dwproton-10.0-26-x86_64.tar.xz",
        )

        assert (
            url
            == "https://dawn.wine/dawn-winery/dwproton/releases/download/dwproton-10.0-26/dwproton-10.0-26-x86_64.tar.xz"
        )


# =============================================================================
# _handle_already_extracted Tests (Phase 3.1)
# =============================================================================


class TestHandleAlreadyExtracted:
    """Tests for the _handle_already_extracted helper method."""

    def test_handle_already_extracted_skips_when_links_up_to_date(
        self,
        mocker: Any,
        mock_network_factory: Any,
        mock_filesystem_factory: Any,
        tmp_path: Path,
    ) -> None:
        """Test _handle_already_extracted returns early when links are up-to-date."""
        mock_network = mock_network_factory()
        mock_fs = mock_filesystem_factory(use_tmp_path=True)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
        )

        mock_manage = mocker.patch.object(
            fetcher.link_manager,
            "manage_proton_links",
        )
        mocker.patch.object(
            fetcher.link_manager,
            "are_links_up_to_date",
            return_value=True,
        )

        result = fetcher._handle_already_extracted(
            extract_dir,
            "GE-Proton10-20",
            ForkName.GE_PROTON,
            version_dir,
            is_manual_release=False,
        )

        assert result == (True, version_dir)
        mock_manage.assert_not_called()

    def test_handle_already_extracted_updates_links_when_needed(
        self,
        mocker: Any,
        mock_network_factory: Any,
        mock_filesystem_factory: Any,
        tmp_path: Path,
    ) -> None:
        """Test _handle_already_extracted updates symlinks when they are stale."""
        mock_network = mock_network_factory()
        mock_fs = mock_filesystem_factory(use_tmp_path=True)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
        )

        mock_manage = mocker.patch.object(
            fetcher.link_manager,
            "manage_proton_links",
        )
        mocker.patch.object(
            fetcher.link_manager,
            "are_links_up_to_date",
            return_value=False,
        )

        result = fetcher._handle_already_extracted(
            extract_dir,
            "GE-Proton10-20",
            ForkName.GE_PROTON,
            version_dir,
            is_manual_release=True,
        )

        assert result == (True, version_dir)
        mock_manage.assert_called_once_with(
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON, is_manual_release=True
        )


# =============================================================================
# update_all_managed_forks Platform Filtering Tests (Phase 2.5)
# =============================================================================


class TestUpdateAllManagedForksPlatformFiltering:
    """Tests verifying update_all_managed_forks filters by platform."""

    def test_github_fetcher_skips_forgejo_forks(
        self,
        mocker: Any,
        mock_network_factory: Any,
        mock_filesystem_factory: Any,
        tmp_path: Path,
    ) -> None:
        """Test GitHubReleaseFetcher.update_all_managed_forks skips Forgejo forks."""
        mock_network = mock_network_factory()
        mock_fs = mock_filesystem_factory(use_tmp_path=True)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        output_dir = tmp_path / "downloads"
        output_dir.mkdir()

        # Create GE-Proton managed links so it's not skipped
        (extract_dir / "GE-Proton").symlink_to(extract_dir / "GE-Proton10-20")
        ge_dir = extract_dir / "GE-Proton10-20"
        ge_dir.mkdir()

        mocker.patch("shutil.which", return_value="/usr/bin/curl")
        mocker.patch.object(
            fetcher := GitHubReleaseFetcher(
                network_client=mock_network,
                file_system_client=mock_fs,
            ),
            "fetch_and_extract",
            return_value=ge_dir,
        )

        result = fetcher.update_all_managed_forks(output_dir, extract_dir)

        # Only GE-Proton should be in results (GitHub platform)
        assert ForkName.GE_PROTON in result
        # DW-Proton should NOT be in results (Forgejo platform)
        assert ForkName.DW_PROTON not in result

    def test_forgejo_fetcher_skips_github_forks(
        self,
        mocker: Any,
        mock_network_factory: Any,
        mock_filesystem_factory: Any,
        tmp_path: Path,
    ) -> None:
        """Test ForgejoReleaseFetcher.update_all_managed_forks skips GitHub forks."""
        mock_network = mock_network_factory()
        mock_fs = mock_filesystem_factory(use_tmp_path=True)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        output_dir = tmp_path / "downloads"
        output_dir.mkdir()

        # Create DW-Proton managed links so it's not skipped
        (extract_dir / "DW-Proton").symlink_to(extract_dir / "dwproton-10.0-26-x86_64")
        dw_dir = extract_dir / "dwproton-10.0-26-x86_64"
        dw_dir.mkdir()

        mocker.patch("shutil.which", return_value="/usr/bin/curl")
        mocker.patch.object(
            fetcher := ForgejoReleaseFetcher(
                network_client=mock_network,
                file_system_client=mock_fs,
            ),
            "fetch_and_extract",
            return_value=dw_dir,
        )

        result = fetcher.update_all_managed_forks(output_dir, extract_dir)

        # Only DW-Proton should be in results (Forgejo platform)
        assert ForkName.DW_PROTON in result
        # GE-Proton should NOT be in results (GitHub platform)
        assert ForkName.GE_PROTON not in result


# =============================================================================
# Dry-Run Workflow Tests (moved from test_cli.py)
# =============================================================================


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
            "protonfetcher.base_release_fetcher.parse_version",
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
            "protonfetcher.base_release_fetcher.parse_version",
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
            "protonfetcher.base_release_fetcher.parse_version",
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
            "protonfetcher.base_release_fetcher.parse_version",
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
            "protonfetcher.base_release_fetcher.parse_version",
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
