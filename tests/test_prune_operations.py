"""Tests for prune_operations submodule.

Tests the standalone prune operation functions independently of LinkManager.
"""

from pathlib import Path

import pytest
from conftest import SymlinkEnvironment

from protonfetcher.common import ForkName
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.prune_operations import (
    compute_prune_plan,
    execute_prune_removals,
    get_installed_versions,
    get_linked_versions,
    prune_releases,
)


class TestGetInstalledVersions:
    """Tests for get_installed_versions function."""

    def test_ge_proton_versions(self, tmp_path: Path) -> None:
        """Test getting GE-Proton installed versions."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for i in range(5, 0, -1):
            v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()

        versions = get_installed_versions(
            extract_dir, ForkName.GE_PROTON, FileSystemClient()
        )

        assert len(versions) == 5
        assert versions[0] == "GE-Proton10-5"
        assert versions[-1] == "GE-Proton10-1"

    def test_proton_em_versions(self, tmp_path: Path) -> None:
        """Test getting Proton-EM installed versions."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for i in range(3, 0, -1):
            v = extract_dir / f"proton-EM-10.0-{i}"
            v.mkdir()

        versions = get_installed_versions(
            extract_dir, ForkName.PROTON_EM, FileSystemClient()
        )

        assert len(versions) == 3
        assert versions[0] == "proton-EM-10.0-3"

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test getting versions from empty directory."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        versions = get_installed_versions(
            extract_dir, ForkName.GE_PROTON, FileSystemClient()
        )

        assert versions == []

    def test_cachyos_versions(self, tmp_path: Path) -> None:
        """Test getting CachyOS installed versions."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        dates = ["20260321", "20260320", "20260228"]
        for date in dates:
            v = extract_dir / f"proton-cachyos-10.0-{date}-slr-x86_64"
            v.mkdir()

        versions = get_installed_versions(
            extract_dir, ForkName.CACHYOS, FileSystemClient()
        )

        assert len(versions) == 3
        assert versions[0] == "proton-cachyos-10.0-20260321-slr-x86_64"


class TestGetLinkedVersions:
    """Tests for get_linked_versions function."""

    def test_linked_versions_ge_proton(self, tmp_path: Path) -> None:
        """Test getting linked versions for GE-Proton."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create version directories
        v1 = extract_dir / "GE-Proton10-5"
        v2 = extract_dir / "GE-Proton10-4"
        v1.mkdir()
        v2.mkdir()

        # Create symlinks
        main_link = extract_dir / "GE-Proton"
        fb_link = extract_dir / "GE-Proton-Fallback"
        main_link.symlink_to(v1)
        fb_link.symlink_to(v2)

        linked = get_linked_versions(
            extract_dir, ForkName.GE_PROTON, FileSystemClient()
        )

        assert "GE-Proton10-5" in linked
        assert "GE-Proton10-4" in linked

    def test_linked_versions_empty(self, tmp_path: Path) -> None:
        """Test getting linked versions when no symlinks exist."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        linked = get_linked_versions(
            extract_dir, ForkName.GE_PROTON, FileSystemClient()
        )

        assert linked == set()

    def test_linked_versions_broken_symlink(self, tmp_path: Path) -> None:
        """Test that broken symlinks are skipped."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create a broken symlink
        main_link = extract_dir / "GE-Proton"
        main_link.symlink_to(extract_dir / "NonExistent")

        linked = get_linked_versions(
            extract_dir, ForkName.GE_PROTON, FileSystemClient()
        )

        assert linked == set()


class TestComputePrunePlan:
    """Tests for compute_prune_plan function."""

    def test_keeps_newest_versions(self, tmp_path: Path) -> None:
        """Test that the newest versions are kept."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for i in range(5, 0, -1):
            v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()

        kept, pruned = compute_prune_plan(
            extract_dir, ForkName.GE_PROTON, keep=3, file_system=FileSystemClient()
        )

        assert len(kept) == 3
        assert "GE-Proton10-5" in kept
        assert "GE-Proton10-4" in kept
        assert "GE-Proton10-3" in kept
        assert len(pruned) == 2
        assert "GE-Proton10-2" in pruned
        assert "GE-Proton10-1" in pruned

    def test_protects_linked_versions(self, tmp_path: Path) -> None:
        """Test that linked versions outside top-N are protected from pruning."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create 5 GE-Proton version directories
        versions = []
        for i in range(5, 0, -1):
            v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()
            versions.append(v)

        # Create symlink pointing to GE-Proton10-2 (older, outside top 3)
        main_link = extract_dir / "GE-Proton"
        main_link.symlink_to(versions[3])  # GE-Proton10-2

        kept, pruned = compute_prune_plan(
            extract_dir, ForkName.GE_PROTON, keep=3, file_system=FileSystemClient()
        )

        # Top 3 newest should be kept
        assert "GE-Proton10-5" in kept
        assert "GE-Proton10-4" in kept
        assert "GE-Proton10-3" in kept

        # GE-Proton10-2 should NOT be pruned (it's linked)
        assert "GE-Proton10-2" not in pruned
        # GE-Proton10-1 should be pruned
        assert "GE-Proton10-1" in pruned

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test prune plan with no versions."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        kept, pruned = compute_prune_plan(
            extract_dir, ForkName.GE_PROTON, keep=3, file_system=FileSystemClient()
        )

        assert kept == []
        assert pruned == []

    def test_all_versions_linked(self, tmp_path: Path) -> None:
        """Test when all versions are linked — nothing to prune."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for i in range(3, 0, -1):
            v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()

        # Link all 3 versions
        main_link = extract_dir / "GE-Proton"
        fb1_link = extract_dir / "GE-Proton-Fallback"
        fb2_link = extract_dir / "GE-Proton-Fallback2"
        main_link.symlink_to(extract_dir / "GE-Proton10-3")
        fb1_link.symlink_to(extract_dir / "GE-Proton10-2")
        fb2_link.symlink_to(extract_dir / "GE-Proton10-1")

        kept, pruned = compute_prune_plan(
            extract_dir, ForkName.GE_PROTON, keep=3, file_system=FileSystemClient()
        )

        assert len(kept) == 3
        assert pruned == []


class TestExecutePruneRemovals:
    """Tests for execute_prune_removals function."""

    def test_removes_pruned_versions(self, tmp_path: Path) -> None:
        """Test that prune removals actually delete directories."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for i in range(5, 0, -1):
            v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()

        execute_prune_removals(
            extract_dir,
            ForkName.GE_PROTON,
            ["GE-Proton10-2", "GE-Proton10-1"],
            FileSystemClient(),
        )

        assert (extract_dir / "GE-Proton10-5").exists()
        assert (extract_dir / "GE-Proton10-4").exists()
        assert (extract_dir / "GE-Proton10-3").exists()
        assert not (extract_dir / "GE-Proton10-2").exists()
        assert not (extract_dir / "GE-Proton10-1").exists()

    def test_handles_empty_list(self, tmp_path: Path) -> None:
        """Test that empty list does nothing."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        execute_prune_removals(extract_dir, ForkName.GE_PROTON, [], FileSystemClient())

        # No error, nothing to do


class TestPruneReleases:
    """Tests for prune_releases function."""

    def test_prune_releases_all_forks(self, tmp_path: Path) -> None:
        """Test pruning for all forks."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create 6 versions for each fork (3 will be kept, 3 pruned)
        for i in range(6, 0, -1):
            if ForkName.GE_PROTON:
                v = extract_dir / f"GE-Proton10-{i}"
            else:
                v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()

        kept, pruned = prune_releases(
            extract_dir, ForkName.GE_PROTON, keep=3, dry_run=True
        )

        assert len(kept) == 3
        assert len(pruned) == 3

    def test_prune_releases_dry_run_no_deletion(self, tmp_path: Path) -> None:
        """Test that dry_run=True doesn't delete anything."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create 6 versions
        for i in range(6, 0, -1):
            v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()

        kept, pruned = prune_releases(
            extract_dir, ForkName.GE_PROTON, keep=3, dry_run=True
        )

        assert len(pruned) == 3
        # All directories should still exist
        for i in range(1, 7):
            assert (extract_dir / f"GE-Proton10-{i}").exists()

    def test_prune_releases_invalid_keep(self, tmp_path: Path) -> None:
        """Test pruning with invalid keep value."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        with pytest.raises(ValueError, match="keep must be at least 1"):
            prune_releases(extract_dir, ForkName.GE_PROTON, keep=0, dry_run=True)

    def test_prune_releases_nothing_to_prune(
        self, symlink_environment: SymlinkEnvironment
    ) -> None:
        """Test pruning when exactly 3 versions exist (nothing to prune)."""
        extract_dir: Path = symlink_environment["extract_dir"]
        fork: ForkName = symlink_environment["fork"]

        kept, pruned = prune_releases(
            extract_dir, fork, keep=3, dry_run=True, file_system=FileSystemClient()
        )

        assert len(kept) == 3
        assert pruned == []

    def test_prune_releases_proton_em(self, tmp_path: Path) -> None:
        """Test pruning Proton-EM versions."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for i in range(5, 0, -1):
            v = extract_dir / f"proton-EM-10.0-{i}"
            v.mkdir()

        kept, pruned = prune_releases(
            extract_dir,
            ForkName.PROTON_EM,
            keep=3,
            dry_run=True,
            file_system=FileSystemClient(),
        )

        assert len(kept) == 3
        assert len(pruned) == 2

    def test_prune_releases_cachyos(self, tmp_path: Path) -> None:
        """Test pruning CachyOS versions."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        dates = ["20260321", "20260320", "20260228", "20260227", "20260207"]
        for date in dates:
            v = extract_dir / f"proton-cachyos-10.0-{date}-slr-x86_64"
            v.mkdir()

        kept, pruned = prune_releases(
            extract_dir,
            ForkName.CACHYOS,
            keep=3,
            dry_run=True,
            file_system=FileSystemClient(),
        )

        assert len(kept) == 3
        assert len(pruned) == 2
        # Newest 3 should be kept
        assert any("20260321" in p for p in kept)
        assert any("20260320" in p for p in kept)
        assert any("20260228" in p for p in kept)

    def test_prune_releases_with_keep_one(self, tmp_path: Path) -> None:
        """Test pruning with keep=1."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for i in range(3, 0, -1):
            v = extract_dir / f"GE-Proton10-{i}"
            v.mkdir()

        kept, pruned = prune_releases(
            extract_dir,
            ForkName.GE_PROTON,
            keep=1,
            dry_run=True,
            file_system=FileSystemClient(),
        )

        assert len(kept) == 1
        assert len(pruned) == 2
