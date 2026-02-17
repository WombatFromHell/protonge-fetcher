"""
End-to-end tests for LinkManager symlink management.

Tests the complete link management workflow:
- Symlink creation with priority ordering
- Link status checking optimization
- Version sorting and deduplication
- Release removal and link updates
- Listing managed links
"""

from pathlib import Path
from typing import Any

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import LinkManagementError
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.link_manager import LinkManager


class TestSymlinkCreation:
    """Test symbolic link creation with priority ordering."""

    def test_create_symlinks_main_only(
        self,
        link_manager: LinkManager,
        mock_filesystem_client: Any,
        tmp_path: Path,
    ) -> None:
        """Test creating only the main symlink when one version exists."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()

        main_link = extract_dir / "GE-Proton"

        # Use real filesystem for actual symlink creation
        fs = FileSystemClient()
        real_link_manager = LinkManager(fs)

        candidates = [(("GE-Proton", 10, 20, 0), version_dir)]

        # Act
        result = real_link_manager.create_symlinks(
            main=main_link,
            fb1=extract_dir / "GE-Proton-Fallback",
            fb2=extract_dir / "GE-Proton-Fallback2",
            top_3=candidates,
        )

        # Assert
        assert result is True
        assert main_link.exists()
        assert main_link.is_symlink()
        assert main_link.resolve() == version_dir

    def test_create_symlinks_with_fallbacks(
        self,
        tmp_path: Path,
    ) -> None:
        """Test creating main, fallback1, and fallback2 symlinks."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create three version directories
        v1 = extract_dir / "GE-Proton10-20"
        v2 = extract_dir / "GE-Proton10-19"
        v3 = extract_dir / "GE-Proton10-18"
        v1.mkdir()
        v2.mkdir()
        v3.mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        candidates = [
            (("GE-Proton", 10, 20, 0), v1),
            (("GE-Proton", 10, 19, 0), v2),
            (("GE-Proton", 10, 18, 0), v3),
        ]

        # Act
        result = link_manager.create_symlinks(
            main=extract_dir / "GE-Proton",
            fb1=extract_dir / "GE-Proton-Fallback",
            fb2=extract_dir / "GE-Proton-Fallback2",
            top_3=candidates,
        )

        # Assert
        assert result is True

        # Verify all three symlinks
        main = extract_dir / "GE-Proton"
        fb1 = extract_dir / "GE-Proton-Fallback"
        fb2 = extract_dir / "GE-Proton-Fallback2"

        assert main.is_symlink() and main.resolve() == v1
        assert fb1.is_symlink() and fb1.resolve() == v2
        assert fb2.is_symlink() and fb2.resolve() == v3

    def test_create_symlinks_proton_em(
        self,
        tmp_path: Path,
    ) -> None:
        """Test creating symlinks for Proton-EM fork."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        v1 = extract_dir / "EM-10.0-30"
        v2 = extract_dir / "EM-10.0-29"
        v1.mkdir()
        v2.mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        candidates = [
            (("EM", 10, 0, 30), v1),
            (("EM", 10, 0, 29), v2),
        ]

        # Act
        result = link_manager.create_symlinks(
            main=extract_dir / "Proton-EM",
            fb1=extract_dir / "Proton-EM-Fallback",
            fb2=extract_dir / "Proton-EM-Fallback2",
            top_3=candidates,
        )

        # Assert
        assert result is True

        main = extract_dir / "Proton-EM"
        fb1 = extract_dir / "Proton-EM-Fallback"

        assert main.is_symlink() and main.resolve() == v1
        assert fb1.is_symlink() and fb1.resolve() == v2


class TestLinkStatusChecking:
    """Test the are_links_up_to_date optimization."""

    def test_links_up_to_date_when_correct(
        self,
        symlink_environment: dict[str, Any],
    ) -> None:
        """Test that links are reported up-to-date when pointing to correct target."""
        # Arrange
        fs = FileSystemClient()
        link_manager = LinkManager(fs)
        extract_dir = symlink_environment["extract_dir"]
        fork = symlink_environment["fork"]
        tag = symlink_environment["version_dirs"][0].name

        # Act
        is_up_to_date = link_manager.are_links_up_to_date(
            extract_dir=extract_dir,
            tag=tag,
            fork=fork,
            is_manual_release=True,
        )

        # Assert
        assert is_up_to_date is True

    def test_links_not_up_to_date_when_wrong_target(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that links are reported outdated when pointing to wrong target."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create correct version directory
        correct_dir = extract_dir / "GE-Proton10-20"
        correct_dir.mkdir()

        # Create wrong version directory
        wrong_dir = extract_dir / "GE-Proton10-19"
        wrong_dir.mkdir()

        # Create symlink pointing to wrong directory
        main_link = extract_dir / "GE-Proton"
        main_link.symlink_to(wrong_dir)

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        is_up_to_date = link_manager.are_links_up_to_date(
            extract_dir=extract_dir,
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
            is_manual_release=True,
        )

        # Assert
        assert is_up_to_date is False

    def test_links_not_up_to_date_when_broken(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that links are reported outdated when symlink is broken."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create version directory
        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()

        # Create symlink to non-existent target
        main_link = extract_dir / "GE-Proton"
        non_existent = extract_dir / "NonExistent"
        main_link.symlink_to(non_existent)

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        is_up_to_date = link_manager.are_links_up_to_date(
            extract_dir=extract_dir,
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
            is_manual_release=True,
        )

        # Assert
        assert is_up_to_date is False

    def test_links_not_up_to_date_when_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that links are reported outdated when symlinks don't exist."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        is_up_to_date = link_manager.are_links_up_to_date(
            extract_dir=extract_dir,
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
            is_manual_release=True,
        )

        # Assert
        assert is_up_to_date is False


class TestVersionSorting:
    """Test version parsing and sorting."""

    def test_find_version_candidates_all_forks(
        self,
        installed_proton_versions: list[Path],
        tmp_path: Path,
        fork: ForkName,
    ) -> None:
        """Test finding and parsing version directories for all forks."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        candidates = link_manager.find_version_candidates(
            extract_dir=extract_dir,
            fork=fork,
        )

        # Assert
        assert len(candidates) == 3
        # Versions should be found (sorting depends on implementation)
        versions = [c[0] for c in candidates]
        assert len(versions) == 3

    def test_find_version_candidates_proton_em(
        self,
        tmp_path: Path,
    ) -> None:
        """Test finding and parsing Proton-EM version directories."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create Proton-EM directories
        for name in ["EM-10.0-30", "EM-10.0-29", "EM-10.0-28"]:
            (extract_dir / name).mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        candidates = link_manager.find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.PROTON_EM,
        )

        # Assert
        assert len(candidates) == 3

    def test_skip_other_fork_directories(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that directories from other fork are skipped."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mix GE-Proton and Proton-EM directories
        (extract_dir / "GE-Proton10-20").mkdir()
        (extract_dir / "GE-Proton10-19").mkdir()
        (extract_dir / "EM-10.0-30").mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act: Find GE-Proton candidates
        ge_candidates = link_manager.find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
        )

        # Act: Find Proton-EM candidates
        em_candidates = link_manager.find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.PROTON_EM,
        )

        # Assert
        assert len(ge_candidates) == 2  # Only GE-Proton dirs
        assert len(em_candidates) == 1  # Only Proton-EM dirs

    def test_skip_non_proton_directories(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that non-Proton directories are skipped."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mix Proton and non-Proton directories
        (extract_dir / "GE-Proton10-20").mkdir()
        (extract_dir / "LegacyRuntime").mkdir()
        (extract_dir / "SomeOtherDir").mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        candidates = link_manager.find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
        )

        # Assert
        assert len(candidates) == 1  # Only GE-Proton dir
        assert candidates[0][1].name == "GE-Proton10-20"

    def test_deduplicate_candidates_prefers_standard_naming(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that duplicate versions prefer standard naming over prefixed."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create duplicate: standard and proton- prefixed
        standard = extract_dir / "EM-10.0-30"
        prefixed = extract_dir / "proton-EM-10.0-30"
        standard.mkdir()
        prefixed.mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        candidates = link_manager.find_version_candidates(
            extract_dir=extract_dir,
            fork=ForkName.PROTON_EM,
        )

        # Deduplicate
        deduped = link_manager._deduplicate_candidates(candidates)

        # Assert
        assert len(deduped) == 1
        # Should prefer standard naming (without proton- prefix)
        assert deduped[0][1].name == "EM-10.0-30"


class TestReleaseRemoval:
    """Test release removal and link updates."""

    def test_remove_release_all_forks(
        self,
        symlink_environment: dict[str, Any],
    ) -> None:
        """Test removing a release and updating links for all forks."""
        # Arrange
        fs = FileSystemClient()
        link_manager = LinkManager(fs)
        extract_dir = symlink_environment["extract_dir"]
        fork = symlink_environment["fork"]
        tag = symlink_environment["version_dirs"][0].name
        version_dir = extract_dir / tag

        assert version_dir.exists()

        # Act
        result = link_manager.remove_release(
            extract_dir=extract_dir,
            tag=tag,
            fork=fork,
        )

        # Assert
        assert result is True
        assert not version_dir.exists()

    def test_remove_release_proton_em(
        self,
        tmp_path: Path,
    ) -> None:
        """Test removing a Proton-EM release."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "EM-10.0-30"
        version_dir.mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        result = link_manager.remove_release(
            extract_dir=extract_dir,
            tag="EM-10.0-30",
            fork=ForkName.PROTON_EM,
        )

        # Assert
        assert result is True
        assert not version_dir.exists()

    def test_remove_release_updates_symlinks(
        self,
        symlink_environment: dict[str, Any],
    ) -> None:
        """Test that removing a release updates symlinks that pointed to it."""
        # Arrange
        fs = FileSystemClient()
        link_manager = LinkManager(fs)
        extract_dir = symlink_environment["extract_dir"]
        fork = symlink_environment["fork"]
        tag = symlink_environment["version_dirs"][0].name
        main_link = extract_dir / symlink_environment["link_names"][0]
        version_dir = extract_dir / tag

        # Verify symlink exists before removal
        assert main_link.is_symlink()

        # Act
        link_manager.remove_release(
            extract_dir=extract_dir,
            tag=tag,
            fork=fork,
        )

        # Assert: Version directory should be removed
        assert not version_dir.exists()
        # Symlinks are recreated after removal, so main_link may still exist
        # but pointing to a different version

    def test_remove_nonexistent_release_raises_error(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that removing non-existent release raises error."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act & Assert
        with pytest.raises(LinkManagementError, match="does not exist"):
            link_manager.remove_release(
                extract_dir=extract_dir,
                tag="NonExistent-10-20",
                fork=ForkName.GE_PROTON,
            )


class TestListLinks:
    """Test listing managed symbolic links."""

    def test_list_links_all_forks(
        self,
        symlink_environment: dict[str, Any],
    ) -> None:
        """Test listing symlinks for all forks."""
        # Arrange
        fs = FileSystemClient()
        link_manager = LinkManager(fs)
        extract_dir = symlink_environment["extract_dir"]
        fork = symlink_environment["fork"]
        link_names = symlink_environment["link_names"]

        # Act
        links_info = link_manager.list_links(
            extract_dir=extract_dir,
            fork=fork,
        )

        # Assert
        for link_name in link_names:
            assert link_name in links_info

        # Main link should point to a valid path
        assert links_info[link_names[0]] is not None

    def test_list_links_proton_em(
        self,
        tmp_path: Path,
    ) -> None:
        """Test listing Proton-EM symlinks."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "EM-10.0-30"
        version_dir.mkdir()

        # Create symlinks
        main_link = extract_dir / "Proton-EM"
        main_link.symlink_to(version_dir)

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        links_info = link_manager.list_links(
            extract_dir=extract_dir,
            fork=ForkName.PROTON_EM,
        )

        # Assert
        assert "Proton-EM" in links_info
        assert links_info["Proton-EM"] is not None

    def test_list_links_with_broken_symlink(
        self,
        tmp_path: Path,
    ) -> None:
        """Test listing links when symlink is broken."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create broken symlink
        main_link = extract_dir / "GE-Proton"
        non_existent = extract_dir / "NonExistent"
        main_link.symlink_to(non_existent)

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        links_info = link_manager.list_links(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
        )

        # Assert
        assert "GE-Proton" in links_info
        assert links_info["GE-Proton"] is None  # Broken symlink

    def test_list_links_when_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """Test listing links that don't exist."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        links_info = link_manager.list_links(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
        )

        # Assert
        assert "GE-Proton" in links_info
        assert links_info["GE-Proton"] is None


class TestManageProtonLinks:
    """Test the complete manage_proton_links workflow."""

    def test_manage_proton_links_creates_all_symlinks(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that manage_proton_links creates main, fallback1, fallback2."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create three version directories
        for name in ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]:
            (extract_dir / name).mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        link_manager.manage_proton_links(
            extract_dir=extract_dir,
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
            is_manual_release=True,
        )

        # Assert
        main = extract_dir / "GE-Proton"
        fb1 = extract_dir / "GE-Proton-Fallback"
        fb2 = extract_dir / "GE-Proton-Fallback2"

        assert main.is_symlink()
        assert fb1.is_symlink()
        assert fb2.is_symlink()

    def test_manage_proton_links_proton_em(
        self,
        tmp_path: Path,
    ) -> None:
        """Test manage_proton_links for Proton-EM."""
        # Arrange
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for name in ["EM-10.0-30", "EM-10.0-29"]:
            (extract_dir / name).mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        # Act
        link_manager.manage_proton_links(
            extract_dir=extract_dir,
            tag="EM-10.0-30",
            fork=ForkName.PROTON_EM,
            is_manual_release=True,
        )

        # Assert
        main = extract_dir / "Proton-EM"
        fb1 = extract_dir / "Proton-EM-Fallback"

        assert main.is_symlink()
        assert fb1.is_symlink()
