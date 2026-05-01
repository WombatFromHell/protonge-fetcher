"""Tests for BaseReleaseFetcher shared workflow methods."""

from pathlib import Path
from typing import Any

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import LinkManagementError, ProtonFetcherError
from protonfetcher.forgejo_fetcher import ForgejoReleaseFetcher


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
