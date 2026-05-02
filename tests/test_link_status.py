"""Tests for link_status submodule.

Tests the standalone link status query functions independently of LinkManager.
"""

from pathlib import Path

from conftest import SymlinkEnvironment  # noqa: E402

from protonfetcher.common import ForkName
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.link_status import (
    build_expected_link_mapping,
    compare_link_targets,
    has_managed_links,
    list_links,
)


class TestListLinks:
    """Tests for list_links function."""

    def test_list_links_all_forks(
        self,
        symlink_environment: SymlinkEnvironment,
    ) -> None:
        """Test listing symlinks for all forks."""
        extract_dir = symlink_environment["extract_dir"]
        fork = symlink_environment["fork"]
        link_names = symlink_environment["link_names"]

        links_info = list_links(
            extract_dir=extract_dir,
            fork=fork,
            file_system=FileSystemClient(),
        )

        for link_name in link_names:
            assert link_name in links_info

        # Main link should point to a valid path
        assert links_info[link_names[0]] is not None

    def test_list_links_proton_em(self, tmp_path: Path) -> None:
        """Test listing Proton-EM symlinks."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "EM-10.0-30"
        version_dir.mkdir()

        main_link = extract_dir / "Proton-EM"
        main_link.symlink_to(version_dir)

        links_info = list_links(
            extract_dir=extract_dir,
            fork=ForkName.PROTON_EM,
            file_system=FileSystemClient(),
        )

        assert "Proton-EM" in links_info
        assert links_info["Proton-EM"] is not None

    def test_list_links_with_broken_symlink(self, tmp_path: Path) -> None:
        """Test listing links when symlink is broken."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        main_link = extract_dir / "GE-Proton"
        non_existent = extract_dir / "NonExistent"
        main_link.symlink_to(non_existent)

        links_info = list_links(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
            file_system=FileSystemClient(),
        )

        assert "GE-Proton" in links_info
        assert links_info["GE-Proton"] is None  # Broken symlink

    def test_list_links_when_missing(self, tmp_path: Path) -> None:
        """Test listing links that don't exist."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        links_info = list_links(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
            file_system=FileSystemClient(),
        )

        assert "GE-Proton" in links_info
        assert links_info["GE-Proton"] is None


class TestHasManagedLinks:
    """Tests for has_managed_links function."""

    def test_has_managed_links_returns_true(self, tmp_path: Path) -> None:
        """Test has_managed_links returns True when symlinks exist."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        version_dir = extract_dir / "GE-Proton10-20"
        version_dir.mkdir()

        main_link = extract_dir / "GE-Proton"
        main_link.symlink_to(version_dir)

        result = has_managed_links(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
            file_system=FileSystemClient(),
        )

        assert result is True

    def test_has_managed_links_returns_false_no_symlinks(self, tmp_path: Path) -> None:
        """Test has_managed_links returns False when no symlinks exist."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        for name in ["GE-Proton10-20", "GE-Proton10-19"]:
            (extract_dir / name).mkdir()

        result = has_managed_links(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
            file_system=FileSystemClient(),
        )

        assert result is False

    def test_has_managed_links_returns_false_empty_directory(
        self, tmp_path: Path
    ) -> None:
        """Test has_managed_links returns False when directory is empty."""
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        result = has_managed_links(
            extract_dir=extract_dir,
            fork=ForkName.GE_PROTON,
            file_system=FileSystemClient(),
        )

        assert result is False


class TestBuildExpectedLinkMapping:
    """Tests for build_expected_link_mapping function."""

    def test_three_candidates(self, tmp_path: Path) -> None:
        """Test building mapping with three versions."""
        v1 = tmp_path / "GE-Proton10-20"
        v2 = tmp_path / "GE-Proton10-19"
        v3 = tmp_path / "GE-Proton10-18"
        v1.mkdir()
        v2.mkdir()
        v3.mkdir()

        link_names = (
            tmp_path / "GE-Proton",
            tmp_path / "GE-Proton-Fallback",
            tmp_path / "GE-Proton-Fallback2",
        )
        top_3 = [
            (("GE-Proton", 10, 20, 0), v1),
            (("GE-Proton", 10, 19, 0), v2),
            (("GE-Proton", 10, 18, 0), v3),
        ]

        mapping = build_expected_link_mapping(link_names, top_3)

        assert len(mapping) == 3
        assert mapping["GE-Proton"] == str(v1)
        assert mapping["GE-Proton-Fallback"] == str(v2)
        assert mapping["GE-Proton-Fallback2"] == str(v3)

    def test_two_candidates(self, tmp_path: Path) -> None:
        """Test building mapping with only two versions."""
        v1 = tmp_path / "GE-Proton10-20"
        v2 = tmp_path / "GE-Proton10-19"
        v1.mkdir()
        v2.mkdir()

        link_names = (
            tmp_path / "GE-Proton",
            tmp_path / "GE-Proton-Fallback",
            tmp_path / "GE-Proton-Fallback2",
        )
        top_3 = [
            (("GE-Proton", 10, 20, 0), v1),
            (("GE-Proton", 10, 19, 0), v2),
        ]

        mapping = build_expected_link_mapping(link_names, top_3)

        assert len(mapping) == 2
        assert "GE-Proton" in mapping
        assert "GE-Proton-Fallback" in mapping
        assert "GE-Proton-Fallback2" not in mapping


class TestCompareLinkTargets:
    """Tests for compare_link_targets function."""

    def test_all_match(self, tmp_path: Path) -> None:
        """Test that matching targets return True."""
        v1 = tmp_path / "GE-Proton10-20"
        v1.mkdir()

        current = {"GE-Proton": str(v1)}
        expected = {"GE-Proton": str(v1)}

        assert compare_link_targets(current, expected) is True

    def test_wrong_target(self, tmp_path: Path) -> None:
        """Test that wrong target returns False."""
        v1 = tmp_path / "GE-Proton10-20"
        v2 = tmp_path / "GE-Proton10-19"
        v1.mkdir()
        v2.mkdir()

        current = {"GE-Proton": str(v1)}
        expected = {"GE-Proton": str(v2)}

        assert compare_link_targets(current, expected) is False

    def test_missing_link_returns_false(self, tmp_path: Path) -> None:
        """Test that missing link returns False."""
        expected = {"GE-Proton": "/some/path"}
        current: dict[str, str | None] = {}

        assert compare_link_targets(current, expected) is False

    def test_broken_link_returns_false(self, tmp_path: Path) -> None:
        """Test that broken symlink (None target) returns False."""
        current = {"GE-Proton": None}
        expected = {"GE-Proton": "/some/path"}

        assert compare_link_targets(current, expected) is False

    def test_nonexistent_target_returns_false(self, tmp_path: Path) -> None:
        """Test that nonexistent target path returns False."""
        current = {"GE-Proton": "/nonexistent/path"}
        expected = {"GE-Proton": "/another/nonexistent/path"}

        assert compare_link_targets(current, expected) is False

    def test_multiple_links_all_match(self, tmp_path: Path) -> None:
        """Test multiple links all matching."""
        v1 = tmp_path / "GE-Proton10-20"
        v2 = tmp_path / "GE-Proton10-19"
        v1.mkdir()
        v2.mkdir()

        current = {
            "GE-Proton": str(v1),
            "GE-Proton-Fallback": str(v2),
        }
        expected = {
            "GE-Proton": str(v1),
            "GE-Proton-Fallback": str(v2),
        }

        assert compare_link_targets(current, expected) is True

    def test_multiple_links_one_mismatch(self, tmp_path: Path) -> None:
        """Test multiple links where one mismatches."""
        v1 = tmp_path / "GE-Proton10-20"
        v2 = tmp_path / "GE-Proton10-19"
        v3 = tmp_path / "GE-Proton10-18"
        v1.mkdir()
        v2.mkdir()
        v3.mkdir()

        current = {
            "GE-Proton": str(v1),
            "GE-Proton-Fallback": str(v2),
        }
        expected = {
            "GE-Proton": str(v1),
            "GE-Proton-Fallback": str(v3),
        }

        assert compare_link_targets(current, expected) is False
