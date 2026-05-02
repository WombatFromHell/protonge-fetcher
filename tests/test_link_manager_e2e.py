"""End-to-end tests for LinkManager orchestration.

Tests the complete link management workflow at the orchestration level.
Unit-level tests for submodules live in their own test files:
- test_version_finder.py
- test_symlink_operations.py
- test_link_status.py
- test_release_operations.py
- test_prune_operations.py
"""

from pathlib import Path

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import LinkManagementError
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.link_manager import LinkManager


class TestLinkStatusChecking:
    """Test the are_links_up_to_date optimization at orchestration level."""

    def test_links_up_to_date_when_correct(
        self,
        symlink_environment: dict,
    ) -> None:
        """Links are up-to-date when pointing to correct target."""
        fs = FileSystemClient()
        link_manager = LinkManager(fs)
        extract_dir = symlink_environment["extract_dir"]
        fork = symlink_environment["fork"]
        tag = symlink_environment["version_dirs"][0].name

        is_up_to_date = link_manager.are_links_up_to_date(
            extract_dir=extract_dir,
            tag=tag,
            fork=fork,
            is_manual_release=True,
        )

        assert is_up_to_date is True

    def test_links_not_up_to_date_when_wrong_target(
        self,
        tmp_path: Path,
    ) -> None:
        """Links are outdated when pointing to wrong target."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        correct_dir = extract_dir / "GE-Proton10-20"
        correct_dir.mkdir()
        wrong_dir = extract_dir / "GE-Proton10-19"
        wrong_dir.mkdir()

        main_link = extract_dir / "GE-Proton"
        main_link.symlink_to(wrong_dir)

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        is_up_to_date = link_manager.are_links_up_to_date(
            extract_dir=extract_dir,
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
            is_manual_release=True,
        )

        assert is_up_to_date is False

    def test_links_not_up_to_date_when_broken(
        self,
        tmp_path: Path,
    ) -> None:
        """Links are outdated when symlink is broken."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()

        main_link = extract_dir / "GE-Proton"
        non_existent = extract_dir / "NonExistent"
        main_link.symlink_to(non_existent)

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        is_up_to_date = link_manager.are_links_up_to_date(
            extract_dir=extract_dir,
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
            is_manual_release=True,
        )

        assert is_up_to_date is False


class TestReleaseRemoval:
    """Test release removal and link updates at orchestration level."""

    def test_remove_release_all_forks(
        self,
        symlink_environment: dict,
    ) -> None:
        """Removing a release and updating links for all forks."""
        fs = FileSystemClient()
        link_manager = LinkManager(fs)
        extract_dir = symlink_environment["extract_dir"]
        fork = symlink_environment["fork"]
        tag = symlink_environment["version_dirs"][0].name
        version_dir = extract_dir / tag

        assert version_dir.exists()

        result = link_manager.remove_release(
            extract_dir=extract_dir,
            tag=tag,
            fork=fork,
        )

        assert result is True
        assert not version_dir.exists()

    def test_remove_release_updates_symlinks(
        self,
        symlink_environment: dict,
    ) -> None:
        """Removing a release updates symlinks that pointed to it."""
        fs = FileSystemClient()
        link_manager = LinkManager(fs)
        extract_dir = symlink_environment["extract_dir"]
        fork = symlink_environment["fork"]
        tag = symlink_environment["version_dirs"][0].name
        main_link = extract_dir / symlink_environment["link_names"][0]
        version_dir = extract_dir / tag

        assert main_link.is_symlink()

        link_manager.remove_release(
            extract_dir=extract_dir,
            tag=tag,
            fork=fork,
        )

        assert not version_dir.exists()

    def test_remove_nonexistent_release_raises_error(
        self,
        tmp_path: Path,
    ) -> None:
        """Removing non-existent release raises error."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        with pytest.raises(LinkManagementError, match="not found"):
            link_manager.remove_release(
                extract_dir=extract_dir,
                tag="NonExistent-10-20",
                fork=ForkName.GE_PROTON,
            )


class TestManageProtonLinks:
    """Test the complete manage_proton_links workflow."""

    def test_manage_proton_links_creates_all_symlinks(
        self,
        tmp_path: Path,
    ) -> None:
        """manage_proton_links creates main, fallback1, fallback2."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for name in ["GE-Proton10-20", "GE-Proton10-19", "GE-Proton10-18"]:
            (extract_dir / name).mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        link_manager.manage_proton_links(
            extract_dir=extract_dir,
            tag="GE-Proton10-20",
            fork=ForkName.GE_PROTON,
            is_manual_release=True,
        )

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
        """manage_proton_links for Proton-EM."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for name in ["EM-10.0-30", "EM-10.0-29"]:
            (extract_dir / name).mkdir()

        fs = FileSystemClient()
        link_manager = LinkManager(fs)

        link_manager.manage_proton_links(
            extract_dir=extract_dir,
            tag="EM-10.0-30",
            fork=ForkName.PROTON_EM,
            is_manual_release=True,
        )

        main = extract_dir / "Proton-EM"
        fb1 = extract_dir / "Proton-EM-Fallback"

        assert main.is_symlink()
        assert fb1.is_symlink()


# =============================================================================
# get_installed_versions Tests (moved from test_cli.py)
# =============================================================================


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
