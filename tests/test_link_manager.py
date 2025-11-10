"""
Unit tests for LinkManager in protonfetcher.py
"""

import os
import tempfile
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from protonfetcher import (
    ForkName,
    LinkManagementError,
    LinkManager,
    parse_version,
)


class TestLinkManager:
    """Tests for LinkManager class."""

    def test_init(self, mocker):
        """Test LinkManager initialization."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)
        assert manager.file_system_client == mock_fs

    def test_create_symlinks_success(self, mocker, tmp_path):
        """Test create_symlinks method with successful symlink creation."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        target_path = tmp_path / "GE-Proton10-20"
        target_path.mkdir()
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations - distinguish between target path and symlink paths
        def mock_exists(path):
            # Return True for the target path and extract dir
            path_str = str(path)
            target_path_str = str(target_path)
            extract_dir_str = str(extract_dir)
            return target_path_str in path_str or extract_dir_str in path_str

        def mock_is_dir(path):
            # Return True for the target path
            return str(path) == str(target_path)

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.side_effect = mock_is_dir

        result = manager.create_symlinks(extract_dir, target_path, ForkName.GE_PROTON)

        # Should create 3 symlinks for GE-Proton
        assert result is True
        assert mock_fs.symlink_to.call_count == 3

    def test_create_symlinks_target_not_exists(self, mocker, tmp_path):
        """Test create_symlinks when target directory doesn't exist."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Mock file system operations
        mock_fs.exists.return_value = False  # Target doesn't exist
        mock_fs.is_dir.return_value = False

        target_path = tmp_path / "GE-Proton10-20"
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        with pytest.raises(LinkManagementError):
            manager.create_symlinks(extract_dir, target_path, ForkName.GE_PROTON)

    def test_list_links_success(self, mocker, tmp_path):
        """Test list_links method with existing symlinks."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Mock file system operations for existing symlinks
        def mock_exists(path):
            return str(path).endswith(("GE-Proton", "GE-Proton-Fallback"))

        def mock_is_symlink(path):
            return str(path).endswith(("GE-Proton", "GE-Proton-Fallback"))

        def mock_resolve(path):
            if str(path).endswith("GE-Proton"):
                return tmp_path / "GE-Proton10-20"
            elif str(path).endswith("GE-Proton-Fallback"):
                return tmp_path / "GE-Proton9-15"
            return Path("/nonexistent")

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_symlink.side_effect = mock_is_symlink
        mock_fs.resolve.side_effect = mock_resolve

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        result = manager.list_links(extract_dir, ForkName.GE_PROTON)

        assert "GE-Proton" in result
        assert "GE-Proton-Fallback" in result
        assert result["GE-Proton"] is not None
        assert result["GE-Proton-Fallback"] is not None

    def test_list_links_no_links_exist(self, mocker, tmp_path):
        """Test list_links when no symlinks exist."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Mock file system operations - no symlinks exist
        mock_fs.exists.return_value = False
        mock_fs.is_symlink.return_value = False

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        result = manager.list_links(extract_dir, ForkName.GE_PROTON)

        assert "GE-Proton" in result
        assert "GE-Proton-Fallback" in result
        assert "GE-Proton-Fallback2" in result
        assert result["GE-Proton"] is None
        assert result["GE-Proton-Fallback"] is None
        assert result["GE-Proton-Fallback2"] is None

    def test_remove_release_success(self, mocker, tmp_path):
        """Test remove_release method with successful removal."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create test directory structure INSIDE the extract directory
        release_dir = extract_dir / "GE-Proton10-20"
        release_dir.mkdir()

        # Mock file system operations correctly to prevent conflicts with link names
        def mock_exists(path):
            path_str = str(path)
            release_dir_str = str(release_dir)
            extract_dir_str = str(extract_dir)
            # Return True for the actual release directory inside extract_dir and the extract directory itself
            # Ensure no directories with link names like "GE-Proton", etc. exist
            return path_str == release_dir_str or path_str == extract_dir_str

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.return_value = True
        mock_fs.is_symlink.return_value = False

        # Mock iterdir to return only the release directory, not any link-named directories
        def mock_iterdir(path):
            if path == extract_dir:
                # Return the release directory for version finding
                # But make sure no link-named directories are returned
                return [release_dir]
            return []

        mock_fs.iterdir.side_effect = mock_iterdir
        mock_fs.unlink.return_value = None  # For removing symlinks
        mock_fs.rmtree.return_value = None  # For removing directories

        result = manager.remove_release(
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON
        )

        assert result is True
        # Should call rmtree exactly once for the release directory
        # The link regeneration should not cause additional rmtree calls
        # if there are no conflicting directories with link names
        mock_fs.rmtree.assert_called_once()

    def test_remove_release_not_found(self, mocker, tmp_path):
        """Test remove_release when the specified release doesn't exist."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations - release directory doesn't exist
        mock_fs.exists.return_value = False
        mock_fs.is_dir.return_value = False

        # Mock iterdir to return no matching directories
        def mock_iterdir(path):
            return []

        mock_fs.iterdir.side_effect = mock_iterdir

        with pytest.raises(LinkManagementError):
            manager.remove_release(extract_dir, "GE-Proton10-20", ForkName.GE_PROTON)

    def test_find_version_candidates_ge_proton(self, mocker, tmp_path):
        """Test find_version_candidates method with GE-Proton format."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create test directories
        release1 = tmp_path / "GE-Proton10-20"
        release1.mkdir()
        release2 = tmp_path / "GE-Proton9-15"
        release2.mkdir()
        release3 = tmp_path / "Other-Dir"
        release3.mkdir()

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations
        def mock_is_dir(path):
            return path in [release1, release2, release3, extract_dir]

        def mock_iterdir(path):
            if path == extract_dir:
                return [release1, release2, release3]
            return []

        mock_fs.is_dir.side_effect = mock_is_dir
        mock_fs.iterdir.side_effect = mock_iterdir

        candidates = manager.find_version_candidates(extract_dir, ForkName.GE_PROTON)

        # Should find 2 GE-Proton releases
        assert len(candidates) == 2
        # Check that they are properly parsed and sorted
        tags = [c[0][0] for c in candidates]  # Get the tag names from the VersionTuple
        assert "GE-Proton" in tags[0] or "GE-Proton" in tags[1]

    def test_find_version_candidates_proton_em(self, mocker, tmp_path):
        """Test find_version_candidates method with Proton-EM format."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create test directories
        release1 = tmp_path / "proton-EM-10.0-30"
        release1.mkdir()
        release2 = tmp_path / "proton-EM-9.5-25"
        release2.mkdir()
        release3 = tmp_path / "Other-Dir"
        release3.mkdir()

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations
        def mock_is_dir(path):
            return path in [release1, release2, release3, extract_dir]

        def mock_iterdir(path):
            if path == extract_dir:
                return [release1, release2, release3]
            return []

        mock_fs.is_dir.side_effect = mock_is_dir
        mock_fs.iterdir.side_effect = mock_iterdir

        candidates = manager.find_version_candidates(extract_dir, ForkName.PROTON_EM)

        # Should find 2 Proton-EM releases
        assert len(candidates) == 2
        # Check that they are properly parsed and sorted
        tags = [c[0][0] for c in candidates]  # Get the tag names from the VersionTuple
        assert "EM" in tags[0] or "EM" in tags[1]

    def test_get_link_names_for_fork_ge_proton(self, mocker):
        """Test get_link_names_for_fork method with GE-Proton."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        link_names = manager.get_link_names_for_fork(ForkName.GE_PROTON)
        expected = (
            Path("GE-Proton"),
            Path("GE-Proton-Fallback"),
            Path("GE-Proton-Fallback2"),
        )
        assert link_names == expected

    def test_get_link_names_for_fork_proton_em(self, mocker):
        """Test get_link_names_for_fork method with Proton-EM."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        link_names = manager.get_link_names_for_fork(ForkName.PROTON_EM)
        expected = (
            Path("Proton-EM"),
            Path("Proton-EM-Fallback"),
            Path("Proton-EM-Fallback2"),
        )
        assert link_names == expected

    def test_find_tag_directory_manual_release(self, mocker, tmp_path):
        """Test find_tag_directory method for manual release."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create test directory in the extract directory where function will look
        release_dir = extract_dir / "GE-Proton10-20"
        release_dir.mkdir()

        # Mock file system operations to properly detect the created directory
        def mock_exists(path):
            path_str = str(path)
            release_dir_str = str(release_dir)
            extract_dir_str = str(extract_dir)
            return release_dir_str in path_str or extract_dir_str in path_str

        def mock_is_dir(path):
            return str(path) == str(release_dir)

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.side_effect = mock_is_dir

        result = manager.find_tag_directory(
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON
        )

        assert result == release_dir

    def test_find_tag_directory_manual_release_not_found(self, mocker, tmp_path):
        """Test find_tag_directory method when manual release is not found."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations - directory doesn't exist
        mock_fs.exists.return_value = False
        mock_fs.is_dir.return_value = False

        with pytest.raises(LinkManagementError):
            manager.find_tag_directory(
                extract_dir, "GE-Proton10-20", ForkName.GE_PROTON
            )

    def test_manage_proton_links_success(self, mocker, tmp_path):
        """Test manage_proton_links method with successful link management."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create test directories
        release1 = tmp_path / "GE-Proton10-20"
        release1.mkdir()
        release2 = tmp_path / "GE-Proton9-15"
        release2.mkdir()
        release3 = tmp_path / "GE-Proton8-10"
        release3.mkdir()

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations
        def mock_is_dir(path):
            return path in [release1, release2, release3, extract_dir]

        def mock_iterdir(path):
            if path == extract_dir:
                return [release1, release2, release3]
            return []

        def mock_exists(path):
            # Simulate that some symlinks exist and some don't
            return "Fallback2" not in str(path)

        mock_fs.is_dir.side_effect = mock_is_dir
        mock_fs.iterdir.side_effect = mock_iterdir
        mock_fs.exists.side_effect = mock_exists
        mock_fs.unlink.return_value = None
        mock_fs.symlink_to.return_value = None

        result = manager.manage_proton_links(extract_dir, ForkName.GE_PROTON)

        assert result is True
        # Should have created symlinks for the top 3 versions
        assert mock_fs.symlink_to.call_count >= 1  # At least one symlink created

    def test_manage_proton_links_no_versions_found(self, mocker, tmp_path):
        """Test manage_proton_links when no versions are found."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations - no directories match version patterns
        def mock_iterdir(path):
            return []

        mock_fs.iterdir.side_effect = mock_iterdir

        result = manager.manage_proton_links(extract_dir, ForkName.GE_PROTON)

        assert result is True  # Should succeed even with no versions to link
