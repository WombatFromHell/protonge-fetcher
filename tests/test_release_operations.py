"""Tests for release_operations submodule.

Tests the standalone release removal functions independently of LinkManager.
"""

from pathlib import Path

import pytest

from protonfetcher.common import ForkName
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.release_operations import (
    _check_release_exists,
    _determine_release_path,
    _identify_links_to_remove,
    _remove_release_directory,
    _remove_symbolic_links,
    cleanup_stale_symlinks,
    remove_release,
)
from tests.fixtures import SymlinkEnvironment


class TestDetermineReleasePath:
    """Tests for _determine_release_path function."""

    def test_ge_proton_path(self, tmp_path: Path) -> None:
        """Test GE-Proton path resolution."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()

        result = _determine_release_path(
            extract_dir=extract_dir,
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
            file_system=FileSystemClient(),
        )

        assert result == version_dir

    def test_proton_em_path(self, tmp_path: Path) -> None:
        """Test Proton-EM path resolution."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "EM-10.0-30"
        version_dir.mkdir()

        result = _determine_release_path(
            extract_dir=extract_dir,
            tag="EM-10.0-30",
            fork=ForkName.PROTON_EM,
            file_system=FileSystemClient(),
        )

        assert result == version_dir

    def test_cachyos_path(self, tmp_path: Path) -> None:
        """Test CachyOS path resolution."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "proton-CachyOS-10-20-x86_64"
        version_dir.mkdir()

        result = _determine_release_path(
            extract_dir=extract_dir,
            tag="CachyOS-10-20",
            fork=ForkName.CACHYOS,
            file_system=FileSystemClient(),
        )

        assert result == version_dir


class TestCheckReleaseExists:
    """Tests for _check_release_exists function."""

    def test_existing_directory_passes(self, tmp_path: Path) -> None:
        """Test that existing directory passes check."""
        release_path = tmp_path / "GE-Proton10-20"
        release_path.mkdir()

        # Should not raise
        _check_release_exists(release_path, FileSystemClient())

    def test_nonexistent_directory_raises(self, tmp_path: Path) -> None:
        """Test that nonexistent directory raises error."""
        release_path = tmp_path / "NonExistent"

        with pytest.raises(Exception, match="does not exist"):
            _check_release_exists(release_path, FileSystemClient())


class TestIdentifyLinksToRemove:
    """Tests for _identify_links_to_remove function."""

    def test_identifies_link_pointing_to_release(
        self, symlink_environment: SymlinkEnvironment
    ) -> None:
        """Test that links pointing to the release are identified."""
        extract_dir = symlink_environment["extract_dir"]
        fork = symlink_environment["fork"]
        version_dirs = symlink_environment["version_dirs"]
        link_names = symlink_environment["link_names"]
        tag = version_dirs[0].name
        release_path = extract_dir / tag

        links_to_remove = _identify_links_to_remove(
            extract_dir=extract_dir,
            release_path=release_path,
            fork=fork,
            file_system=FileSystemClient(),
        )

        # Main link should be identified
        main_link = extract_dir / link_names[0]
        assert main_link in links_to_remove

    def test_skips_broken_link(self, tmp_path: Path) -> None:
        """Test that broken symlinks are not identified for removal.

        Broken symlinks (pointing to non-existent targets) cannot be resolved
        to the release path, so they should not be included.
        """
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        release_path = extract_dir / "GE-Proton10-20"
        release_path.mkdir()

        # Create a broken symlink (pointing to non-existent target)
        main_link = extract_dir / "GE-Proton"
        non_existent = extract_dir / "NonExistent"
        main_link.symlink_to(non_existent)

        links_to_remove = _identify_links_to_remove(
            extract_dir=extract_dir,
            release_path=release_path,
            fork=ForkName.GE_PROTON,
            file_system=FileSystemClient(),
        )

        # Broken symlink should NOT be identified (can't match release_path)
        assert main_link not in links_to_remove

    def test_no_links_returns_empty(self, tmp_path: Path) -> None:
        """Test that no links returns empty list."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        release_path = extract_dir / "GE-Proton10-20"
        release_path.mkdir()

        links_to_remove = _identify_links_to_remove(
            extract_dir=extract_dir,
            release_path=release_path,
            fork=ForkName.GE_PROTON,
            file_system=FileSystemClient(),
        )

        assert links_to_remove == []

    def test_only_identifies_matching_links(self, tmp_path: Path) -> None:
        """Test that only links pointing to the release are identified."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        release_path = extract_dir / "GE-Proton10-20"
        release_path.mkdir()

        other_dir = extract_dir / "GE-Proton10-19"
        other_dir.mkdir()

        # Create link pointing to other directory
        main_link = extract_dir / "GE-Proton"
        main_link.symlink_to(other_dir)

        links_to_remove = _identify_links_to_remove(
            extract_dir=extract_dir,
            release_path=release_path,
            fork=ForkName.GE_PROTON,
            file_system=FileSystemClient(),
        )

        # Link pointing to other directory should NOT be identified
        assert main_link not in links_to_remove


class TestRemoveReleaseDirectory:
    """Tests for _remove_release_directory function."""

    def test_removes_directory(self, tmp_path: Path) -> None:
        """Test that directory is removed."""
        release_path = tmp_path / "GE-Proton10-20"
        release_path.mkdir()

        _remove_release_directory(release_path, FileSystemClient())

        assert not release_path.exists()

    def test_raises_on_failure(self, tmp_path: Path) -> None:
        """Test that removal failure raises LinkManagementError."""
        release_path = tmp_path / "GE-Proton10-20"
        release_path.mkdir()

        # Make directory read-only to force failure
        release_path.chmod(0o000)

        try:
            with pytest.raises(Exception, match="Failed to remove"):
                _remove_release_directory(release_path, FileSystemClient())
        finally:
            release_path.chmod(0o755)


class TestRemoveSymbolicLinks:
    """Tests for _remove_symbolic_links function."""

    def test_removes_links(self, tmp_path: Path) -> None:
        """Test that symlinks are removed."""
        version_dir = tmp_path / "GE-Proton10-20"
        version_dir.mkdir()

        main_link = tmp_path / "GE-Proton"
        main_link.symlink_to(version_dir)

        fb1_link = tmp_path / "GE-Proton-Fallback"
        fb1_link.symlink_to(version_dir)

        _remove_symbolic_links([main_link, fb1_link], FileSystemClient())

        assert not main_link.exists()
        assert not fb1_link.exists()

    def test_handles_empty_list(self, tmp_path: Path) -> None:
        """Test that empty list does nothing."""
        _remove_symbolic_links([], FileSystemClient())


class TestRemoveRelease:
    """Tests for remove_release function."""

    def test_remove_release_all_forks(
        self, symlink_environment: SymlinkEnvironment
    ) -> None:
        """Test removing a release and updating links for all forks."""
        extract_dir = symlink_environment["extract_dir"]
        fork = symlink_environment["fork"]
        version_dirs = symlink_environment["version_dirs"]
        tag = version_dirs[0].name
        version_dir = extract_dir / tag

        assert version_dir.exists()

        result = remove_release(
            extract_dir=extract_dir,
            tag=tag,
            fork=fork,
            file_system=FileSystemClient(),
        )

        assert result is True
        assert not version_dir.exists()

    def test_remove_release_proton_em(self, tmp_path: Path) -> None:
        """Test removing a Proton-EM release."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "EM-10.0-30"
        version_dir.mkdir()

        result = remove_release(
            extract_dir=extract_dir,
            tag="EM-10.0-30",
            fork=ForkName.PROTON_EM,
            file_system=FileSystemClient(),
        )

        assert result is True
        assert not version_dir.exists()

    def test_remove_nonexistent_release_raises_error(self, tmp_path: Path) -> None:
        """Test that removing non-existent release raises error."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        with pytest.raises(Exception, match="not found"):
            remove_release(
                extract_dir=extract_dir,
                tag="NonExistent-10-20",
                fork=ForkName.GE_PROTON,
                file_system=FileSystemClient(),
            )


class TestCleanupStaleSymlinks:
    """Tests for symlink cleanup after --rm."""

    def test_removes_dangling_symlink(self, tmp_path: Path) -> None:
        """Test that dangling symlinks (target gone) are removed."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create a version directory and a symlink to it
        v1 = extract_dir / "GE-Proton10-5"
        v1.mkdir()
        main_link = extract_dir / "GE-Proton"
        main_link.symlink_to(v1)

        # Remove the target directory
        v1.rmdir()

        # Run cleanup
        from protonfetcher.filesystem import FileSystemClient

        cleanup_stale_symlinks(extract_dir, ForkName.GE_PROTON, FileSystemClient())

        # Symlink should be gone
        assert not main_link.exists()
        assert not main_link.is_symlink()

    def test_updates_stale_symlink(self, tmp_path: Path) -> None:
        """Test that symlinks pointing to non-top-N releases are updated."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create two versions
        v1 = extract_dir / "GE-Proton10-5"
        v2 = extract_dir / "GE-Proton10-4"
        v1.mkdir()
        v2.mkdir()

        # Symlink points to older version
        main_link = extract_dir / "GE-Proton"
        main_link.symlink_to(v2)

        cleanup_stale_symlinks(extract_dir, ForkName.GE_PROTON, FileSystemClient())

        # Symlink should now point to newest version
        assert main_link.resolve() == v1

    def test_skips_valid_symlink(self, tmp_path: Path) -> None:
        """Test that symlinks pointing to top-N releases are left alone."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        v1 = extract_dir / "GE-Proton10-5"
        v1.mkdir()

        main_link = extract_dir / "GE-Proton"
        main_link.symlink_to(v1)

        cleanup_stale_symlinks(extract_dir, ForkName.GE_PROTON, FileSystemClient())

        # Symlink should still point to v1
        assert main_link.resolve() == v1
