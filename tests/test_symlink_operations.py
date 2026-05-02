"""Tests for symlink_operations submodule.

Tests the standalone symlink creation, cleanup, and comparison functions
independently of LinkManager orchestration.
"""

from pathlib import Path

from protonfetcher.filesystem import FileSystemClient
from protonfetcher.symlink_operations import (
    cleanup_unwanted_links,
    compare_targets,
    create_symlink_specs,
    create_symlinks,
    handle_existing_symlink,
)


class TestCreateSymlinkSpecs:
    """Tests for create_symlink_specs function."""

    def test_one_candidate(self, tmp_path: Path) -> None:
        """Test creating specs with only one version."""
        v1 = tmp_path / "GE-Proton10-20"
        v1.mkdir()
        candidates = [(("GE-Proton", 10, 20, 0), v1)]

        specs = create_symlink_specs(
            main=tmp_path / "GE-Proton",
            fb1=tmp_path / "GE-Proton-Fallback",
            fb2=tmp_path / "GE-Proton-Fallback2",
            top_3=candidates,
        )

        assert len(specs) == 1
        assert specs[0].link_path.name == "GE-Proton"
        assert specs[0].target_path == v1
        assert specs[0].priority == 0

    def test_two_candidates(self, tmp_path: Path) -> None:
        """Test creating specs with two versions."""
        v1 = tmp_path / "GE-Proton10-20"
        v2 = tmp_path / "GE-Proton10-19"
        v1.mkdir()
        v2.mkdir()
        candidates = [
            (("GE-Proton", 10, 20, 0), v1),
            (("GE-Proton", 10, 19, 0), v2),
        ]

        specs = create_symlink_specs(
            main=tmp_path / "GE-Proton",
            fb1=tmp_path / "GE-Proton-Fallback",
            fb2=tmp_path / "GE-Proton-Fallback2",
            top_3=candidates,
        )

        assert len(specs) == 2
        assert specs[0].link_path.name == "GE-Proton"
        assert specs[1].link_path.name == "GE-Proton-Fallback"

    def test_three_candidates(self, tmp_path: Path) -> None:
        """Test creating specs with three versions."""
        v1 = tmp_path / "GE-Proton10-20"
        v2 = tmp_path / "GE-Proton10-19"
        v3 = tmp_path / "GE-Proton10-18"
        v1.mkdir()
        v2.mkdir()
        v3.mkdir()
        candidates = [
            (("GE-Proton", 10, 20, 0), v1),
            (("GE-Proton", 10, 19, 0), v2),
            (("GE-Proton", 10, 18, 0), v3),
        ]

        specs = create_symlink_specs(
            main=tmp_path / "GE-Proton",
            fb1=tmp_path / "GE-Proton-Fallback",
            fb2=tmp_path / "GE-Proton-Fallback2",
            top_3=candidates,
        )

        assert len(specs) == 3
        assert specs[0].priority == 0
        assert specs[1].priority == 1
        assert specs[2].priority == 2


class TestCreateSymlinks:
    """Tests for create_symlinks function."""

    def test_create_symlinks_main_only(self, tmp_path: Path) -> None:
        """Test creating only the main symlink when one version exists."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()

        candidates = [(("GE-Proton", 10, 20, 0), version_dir)]

        result = create_symlinks(
            main=extract_dir / "GE-Proton",
            fb1=extract_dir / "GE-Proton-Fallback",
            fb2=extract_dir / "GE-Proton-Fallback2",
            top_3=candidates,
            file_system=FileSystemClient(),
        )

        assert result is True
        main_link = extract_dir / "GE-Proton"
        assert main_link.exists()
        assert main_link.is_symlink()
        assert main_link.resolve() == version_dir

    def test_create_symlinks_with_fallbacks(self, tmp_path: Path) -> None:
        """Test creating main, fallback1, and fallback2 symlinks."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        v1 = extract_dir / "GE-Proton10-20"
        v2 = extract_dir / "GE-Proton10-19"
        v3 = extract_dir / "GE-Proton10-18"
        v1.mkdir()
        v2.mkdir()
        v3.mkdir()

        candidates = [
            (("GE-Proton", 10, 20, 0), v1),
            (("GE-Proton", 10, 19, 0), v2),
            (("GE-Proton", 10, 18, 0), v3),
        ]

        result = create_symlinks(
            main=extract_dir / "GE-Proton",
            fb1=extract_dir / "GE-Proton-Fallback",
            fb2=extract_dir / "GE-Proton-Fallback2",
            top_3=candidates,
            file_system=FileSystemClient(),
        )

        assert result is True

        main = extract_dir / "GE-Proton"
        fb1 = extract_dir / "GE-Proton-Fallback"
        fb2 = extract_dir / "GE-Proton-Fallback2"

        assert main.is_symlink() and main.resolve() == v1
        assert fb1.is_symlink() and fb1.resolve() == v2
        assert fb2.is_symlink() and fb2.resolve() == v3

    def test_create_symlinks_proton_em(self, tmp_path: Path) -> None:
        """Test creating symlinks for Proton-EM fork."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        v1 = extract_dir / "EM-10.0-30"
        v2 = extract_dir / "EM-10.0-29"
        v1.mkdir()
        v2.mkdir()

        candidates = [
            (("EM", 10, 0, 30), v1),
            (("EM", 10, 0, 29), v2),
        ]

        result = create_symlinks(
            main=extract_dir / "Proton-EM",
            fb1=extract_dir / "Proton-EM-Fallback",
            fb2=extract_dir / "Proton-EM-Fallback2",
            top_3=candidates,
            file_system=FileSystemClient(),
        )

        assert result is True

        main = extract_dir / "Proton-EM"
        fb1 = extract_dir / "Proton-EM-Fallback"

        assert main.is_symlink() and main.resolve() == v1
        assert fb1.is_symlink() and fb1.resolve() == v2


class TestCleanupUnwantedLinks:
    """Tests for cleanup_unwanted_links function."""

    def test_removes_unwanted_symlink(self, tmp_path: Path) -> None:
        """Test that symlinks not in wants are removed."""
        fs = FileSystemClient()
        main = tmp_path / "GE-Proton"
        fb1 = tmp_path / "GE-Proton-Fallback"
        fb2 = tmp_path / "GE-Proton-Fallback2"

        # Create all three symlinks
        v1 = tmp_path / "GE-Proton10-20"
        v1.mkdir()
        fs.symlink_to(main, v1, target_is_directory=True)
        fs.symlink_to(fb1, v1, target_is_directory=True)
        fs.symlink_to(fb2, v1, target_is_directory=True)

        # Only want main
        wants = {main: v1}
        cleanup_unwanted_links(main, fb1, fb2, wants, fs)

        assert main.is_symlink()
        assert not fb1.exists()
        assert not fb2.exists()

    def test_removes_conflicting_directory(self, tmp_path: Path) -> None:
        """Test that real directories conflicting with wanted symlinks are removed."""
        fs = FileSystemClient()
        main = tmp_path / "GE-Proton"
        fb1 = tmp_path / "GE-Proton-Fallback"
        fb2 = tmp_path / "GE-Proton-Fallback2"

        # Create a real directory at fb1
        fb1.mkdir()

        wants = {main: tmp_path / "GE-Proton10-20"}
        cleanup_unwanted_links(main, fb1, fb2, wants, fs)

        assert not fb1.exists()


class TestCompareTargets:
    """Tests for compare_targets function."""

    def test_matching_targets(self, tmp_path: Path) -> None:
        """Test that matching paths return True."""
        fs = FileSystemClient()
        v1 = tmp_path / "GE-Proton10-20"
        v1.mkdir()
        assert compare_targets(v1, v1, fs) is True

    def test_different_targets(self, tmp_path: Path) -> None:
        """Test that different paths return False."""
        fs = FileSystemClient()
        v1 = tmp_path / "GE-Proton10-20"
        v2 = tmp_path / "GE-Proton10-19"
        v1.mkdir()
        v2.mkdir()
        assert compare_targets(v1, v2, fs) is False

    def test_nonexistent_target_returns_false(self, tmp_path: Path) -> None:
        """Test that nonexistent target returns False."""
        fs = FileSystemClient()
        v1 = tmp_path / "GE-Proton10-20"
        v1.mkdir()
        nonexistent = tmp_path / "GE-Proton99-99"
        assert compare_targets(v1, nonexistent, fs) is False


class TestHandleExistingSymlink:
    """Tests for handle_existing_symlink function."""

    def test_correct_symlink_unchanged(self, tmp_path: Path) -> None:
        """Test that correct symlink is not modified."""
        fs = FileSystemClient()
        link = tmp_path / "GE-Proton"
        v1 = tmp_path / "GE-Proton10-20"
        v1.mkdir()
        fs.symlink_to(link, v1, target_is_directory=True)

        handle_existing_symlink(link, v1, fs)

        assert link.is_symlink()
        assert link.resolve() == v1

    def test_wrong_symlink_removed(self, tmp_path: Path) -> None:
        """Test that wrong symlink is removed."""
        fs = FileSystemClient()
        link = tmp_path / "GE-Proton"
        v1 = tmp_path / "GE-Proton10-20"
        v2 = tmp_path / "GE-Proton10-19"
        v1.mkdir()
        v2.mkdir()
        fs.symlink_to(link, v1, target_is_directory=True)

        handle_existing_symlink(link, v2, fs)

        assert not link.exists()

    def test_broken_symlink_removed(self, tmp_path: Path) -> None:
        """Test that broken symlink is removed."""
        fs = FileSystemClient()
        link = tmp_path / "GE-Proton"
        v1 = tmp_path / "GE-Proton10-20"
        v1.mkdir()
        fs.symlink_to(link, v1, target_is_directory=True)
        # Remove the target to create a broken symlink
        v1.rmdir()

        handle_existing_symlink(link, v1, fs)

        assert not link.exists()
