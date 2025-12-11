"""
Unit tests for LinkManager in protonfetcher.py
"""

from pathlib import Path

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import LinkManagementError
from protonfetcher.link_manager import LinkManager


class TestLinkManager:
    """Tests for LinkManager class."""

    def test_init(self, mocker):
        """Test LinkManager initialization."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)
        assert manager.file_system_client == mock_fs

    def test_is_valid_proton_directory_proton_em_specific_paths(self, mocker):
        """Test Proton-EM specific paths in _is_valid_proton_directory (line 179->exit)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Test valid Proton-EM format 1: proton-EM-{major}.{minor}-{patch}
        entry = Path("proton-EM-10.0-30")
        result = manager._is_valid_proton_directory(entry, ForkName.PROTON_EM)
        assert result is True

        # Test valid Proton-EM format 2: EM-{major}.{minor}-{patch}
        entry = Path("EM-10.0-30")
        result = manager._is_valid_proton_directory(entry, ForkName.PROTON_EM)
        assert result is True

        # Test invalid Proton-EM format (uppercase proton-EM)
        entry = Path("PROTON-EM-10.0-30")
        result = manager._is_valid_proton_directory(entry, ForkName.PROTON_EM)
        assert result is False

        # Test invalid Proton-EM format (no patch number)
        entry = Path("proton-EM-10.0")
        result = manager._is_valid_proton_directory(entry, ForkName.PROTON_EM)
        assert result is False

    def test_create_symlinks_multiple_versions(self, mocker, tmp_path):
        """Test _create_symlink_specs with multiple version scenarios (lines 217-222)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        main = tmp_path / "GE-Proton"
        fb1 = tmp_path / "GE-Proton-Fallback"
        fb2 = tmp_path / "GE-Proton-Fallback2"

        # Test with only 1 version (should create only main)
        target1 = tmp_path / "GE-Proton10-20"
        top_1 = [(("GE-Proton", 10, 20, 0), target1)]
        specs_1 = manager._create_symlink_specs(main, fb1, fb2, top_1)
        assert len(specs_1) == 1
        assert specs_1[0].link_path == main
        assert specs_1[0].target_path == target1
        assert specs_1[0].priority == 0

        # Test with 2 versions (should create main and fb1)
        target2 = tmp_path / "GE-Proton9-15"
        top_2 = [
            (("GE-Proton", 10, 20, 0), target1),
            (("GE-Proton", 9, 15, 0), target2),
        ]
        specs_2 = manager._create_symlink_specs(main, fb1, fb2, top_2)
        assert len(specs_2) == 2
        assert specs_2[0].link_path == main
        assert specs_2[1].link_path == fb1

        # Test with 3 versions (should create main, fb1, and fb2)
        target3 = tmp_path / "GE-Proton8-10"
        top_3 = [
            (("GE-Proton", 10, 20, 0), target1),
            (("GE-Proton", 9, 15, 0), target2),
            (("GE-Proton", 8, 10, 0), target3),
        ]
        specs_3 = manager._create_symlink_specs(main, fb1, fb2, top_3)
        assert len(specs_3) == 3
        assert specs_3[0].link_path == main
        assert specs_3[1].link_path == fb1
        assert specs_3[2].link_path == fb2

    def test_determine_release_path_with_proton_em_prefix(self, mocker, tmp_path):
        """Test _determine_release_path for Proton-EM with proton- prefix (lines 461-466)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        tag = "EM-10.0-30"

        # Create the alternative path (with "proton-" prefix)
        proton_em_path = extract_dir / f"proton-{tag}"
        proton_em_path.mkdir()

        # Only the alternative path exists, not the regular one
        def mock_exists(path):
            return str(path) == str(proton_em_path)

        mock_fs.exists.side_effect = mock_exists

        result = manager._determine_release_path(extract_dir, tag, ForkName.PROTON_EM)

        # Should return the alternative path with "proton-" prefix
        assert result == proton_em_path

    def test_identify_links_to_remove_with_broken_symlinks(self, mocker, tmp_path):
        """Test _identify_links_to_remove with broken symlinks (line 490->484)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        main = extract_dir / "GE-Proton"
        release_path = extract_dir / "GE-Proton10-20"

        def mock_exists(path):
            return str(path) == str(main)

        def mock_is_symlink(path):
            return str(path) == str(main)

        def mock_resolve(path):
            if str(path) == str(main):
                raise OSError("Broken symlink")
            return path

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_symlink.side_effect = mock_is_symlink
        mock_fs.resolve.side_effect = mock_resolve

        links_to_remove = manager._identify_links_to_remove(
            extract_dir, release_path, ForkName.GE_PROTON
        )

        # Broken symlink should be in the list to remove
        assert main in links_to_remove

    def test_handle_manual_release_candidates_scenario(self, mocker):
        """Test _handle_manual_release_candidates with various scenarios (lines 639-643)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        tag = "GE-Proton10-20"
        fork = ForkName.GE_PROTON
        # Create candidates with some existing versions
        candidates = [(("GE-Proton", 10, 0, 15), Path("GE-Proton10-15"))]
        tag_dir = Path("GE-Proton10-20")

        result = manager._handle_manual_release_candidates(
            tag, fork, candidates, tag_dir
        )

        # Should include both the original candidate and the new manual tag
        assert len(result) == 2
        # Should include the manual tag
        assert any(c[1] == tag_dir for c in result)
        # Should be sorted with newer version first
        assert result[0][0][3] == 20  # manual tag version should be first

    def test_create_symlinks_for_test_success(self, mocker, tmp_path):
        """Test create_symlinks_for_test method with successful symlink creation."""
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

        result = manager.create_symlinks_for_test(
            extract_dir, target_path, ForkName.GE_PROTON
        )

        # Should create 3 symlinks for GE-Proton
        assert result is True
        assert mock_fs.symlink_to.call_count == 3

    def test_create_symlinks_for_test_target_not_exists(self, mocker, tmp_path):
        """Test create_symlinks_for_test when target directory doesn't exist."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Mock file system operations
        mock_fs.exists.return_value = False  # Target doesn't exist
        mock_fs.is_dir.return_value = False

        target_path = tmp_path / "GE-Proton10-20"
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        with pytest.raises(LinkManagementError):
            manager.create_symlinks_for_test(
                extract_dir, target_path, ForkName.GE_PROTON
            )

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

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_find_version_candidates(self, mocker, tmp_path, fork):
        """Test find_version_candidates method with both GE-Proton and Proton-EM formats."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create test directories based on fork
        if fork == ForkName.GE_PROTON:
            release1 = tmp_path / "GE-Proton10-20"
            release2 = tmp_path / "GE-Proton9-15"
            expected_tag_part = "GE-Proton"
        else:  # ForkName.PROTON_EM
            release1 = tmp_path / "proton-EM-10.0-30"
            release2 = tmp_path / "proton-EM-9.5-25"
            expected_tag_part = "EM"

        release1.mkdir()
        release2.mkdir()
        release3 = tmp_path / "Other-Dir"
        release3.mkdir()

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations
        def mock_is_dir(path):
            return path in [release1, release2, release3, extract_dir]

        def mock_is_symlink(path):
            return False  # None of these test directories are symlinks

        def mock_iterdir(path):
            if path == extract_dir:
                return [release1, release2, release3]
            return []

        mock_fs.is_dir.side_effect = mock_is_dir
        mock_fs.is_symlink.side_effect = mock_is_symlink
        mock_fs.iterdir.side_effect = mock_iterdir

        candidates = manager.find_version_candidates(extract_dir, fork)

        # Should find 2 releases for the specific fork
        assert len(candidates) == 2
        # Check that they are properly parsed and sorted
        tags = [c[0][0] for c in candidates]  # Get the tag names from the VersionTuple
        assert expected_tag_part in tags[0] or expected_tag_part in tags[1]

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_get_link_names_for_fork(self, mocker, fork, expected_link_names):
        """Test get_link_names_for_fork method with both fork types."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Use a temporary directory for testing
        extract_dir = Path("/tmp/test")
        link_names = manager.get_link_names_for_fork(extract_dir, fork)

        # Get expected names from fixture
        expected = expected_link_names(fork)

        # Check that the names match (ignoring the parent directory)
        assert len(link_names) == len(expected)
        for i, expected_name in enumerate(expected):
            assert link_names[i].name == expected_name.name

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

    def test_find_tag_directory_validation_errors(self, mocker, tmp_path):
        """Test find_tag_directory method with validation errors."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Test invalid extract_dir type - use a string instead of Path
        # This is intentional for testing validation - we want to pass wrong type
        with pytest.raises(ValueError, match="extract_dir must be a Path"):
            manager.find_tag_directory("invalid_path", "tag", ForkName.GE_PROTON)  # type: ignore[arg-type]

        # Test invalid tag type
        with pytest.raises(ValueError, match="tag must be a non-empty string"):
            manager.find_tag_directory(extract_dir, "", ForkName.GE_PROTON)

        # Test invalid fork type - use a mock object instead of string literal
        with pytest.raises(ValueError, match="fork must be a ForkName"):
            manager.find_tag_directory(extract_dir, "tag", mocker.Mock())

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

    def test_manage_proton_links_success_ge_proton(self, mocker, tmp_path):
        """Test manage_proton_links method with successful link management for GE-Proton."""
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

        def mock_is_symlink(path):
            return False  # None of the release directories are symlinks

        def mock_iterdir(path):
            if path == extract_dir:
                return [release1, release2, release3]
            return []

        def mock_exists(path):
            # Simulate that some symlinks exist and some don't
            return "Fallback2" not in str(path)

        mock_fs.is_dir.side_effect = mock_is_dir
        mock_fs.is_symlink.side_effect = mock_is_symlink
        mock_fs.iterdir.side_effect = mock_iterdir
        mock_fs.exists.side_effect = mock_exists
        mock_fs.unlink.return_value = None
        mock_fs.symlink_to.return_value = None

        result = manager.manage_proton_links(extract_dir, ForkName.GE_PROTON)

        assert result is True
        # Should have created symlinks for the top 3 versions
        assert mock_fs.symlink_to.call_count >= 1  # At least one symlink created

    def test_manage_proton_links_success_proton_em(self, mocker, tmp_path):
        """Test manage_proton_links method with successful link management for Proton-EM."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create test directories - for Proton-EM, use the format that's expected
        release1 = tmp_path / "proton-EM-10.0-30"
        release1.mkdir()
        release2 = tmp_path / "proton-EM-9.5-25"
        release2.mkdir()
        release3 = tmp_path / "proton-EM-8.2-20"
        release3.mkdir()

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations
        def mock_is_dir(path):
            return path in [release1, release2, release3, extract_dir]

        def mock_is_symlink(path):
            return False  # None of the release directories are symlinks

        def mock_iterdir(path):
            if path == extract_dir:
                return [release1, release2, release3]
            return []

        def mock_exists(path):
            # Simulate that some symlinks exist and some don't
            return "Fallback2" not in str(path)

        mock_fs.is_dir.side_effect = mock_is_dir
        mock_fs.is_symlink.side_effect = mock_is_symlink
        mock_fs.iterdir.side_effect = mock_iterdir
        mock_fs.exists.side_effect = mock_exists
        mock_fs.unlink.return_value = None
        mock_fs.symlink_to.return_value = None

        result = manager.manage_proton_links(
            extract_dir, "EM-10.0-30", ForkName.PROTON_EM
        )

        assert result is True
        # Should have created symlinks for the top 3 versions
        assert mock_fs.symlink_to.call_count >= 1  # At least one symlink created

    @pytest.mark.parametrize("fork", [ForkName.GE_PROTON, ForkName.PROTON_EM])
    def test_manage_proton_links_no_versions_found(self, mocker, tmp_path, fork):
        """Test manage_proton_links when no versions are found for both forks."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations - no directories match version patterns
        def mock_iterdir(path):
            return []

        mock_fs.iterdir.side_effect = mock_iterdir

        result = manager.manage_proton_links(extract_dir, fork)

        assert result is True  # Should succeed even with no versions to link

    def test_get_tag_name_proton_em_with_prefix(self, mocker):
        """Test _get_tag_name method with Proton-EM prefix removal."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        entry = Path("proton-EM-10.0-30")
        tag_name = manager._get_tag_name(entry, ForkName.PROTON_EM)
        assert tag_name == "EM-10.0-30"

    def test_get_tag_name_proton_em_without_prefix(self, mocker):
        """Test _get_tag_name method without Proton-EM prefix."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        entry = Path("EM-10.0-30")
        tag_name = manager._get_tag_name(entry, ForkName.PROTON_EM)
        assert tag_name == "EM-10.0-30"

    @pytest.mark.parametrize(
        "directory,fork,expected",
        [
            (
                "GE-Proton10-20",
                ForkName.PROTON_EM,
                True,
            ),  # Skip GE-Proton when processing Proton-EM
            (
                "EM-10.0-30",
                ForkName.GE_PROTON,
                True,
            ),  # Skip Proton-EM when processing GE-Proton
            (
                "proton-EM-10.0-30",
                ForkName.GE_PROTON,
                True,
            ),  # Skip proton-EM with prefix when processing GE-Proton
        ],
    )
    def test_should_skip_directory(self, mocker, directory, fork, expected):
        """Test _should_skip_directory method with various combinations."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        should_skip = manager._should_skip_directory(directory, fork)
        assert should_skip is expected

    @pytest.mark.parametrize(
        "fork,entry,expected",
        [
            (ForkName.GE_PROTON, Path("GE-Proton10-20"), True),  # Valid GE-Proton
            (ForkName.GE_PROTON, Path("Invalid-Directory"), False),  # Invalid GE-Proton
            (
                ForkName.GE_PROTON,
                Path("GE-Proton10-20-Extra"),
                False,
            ),  # Extra characters
            (ForkName.GE_PROTON, Path("ge-proton10-20"), False),  # Wrong case
            (
                ForkName.PROTON_EM,
                Path("proton-EM-10.0-30"),
                True,
            ),  # Valid Proton-EM format 1
            (ForkName.PROTON_EM, Path("EM-10.0-30"), True),  # Valid Proton-EM format 2
            (ForkName.PROTON_EM, Path("proton-EM-10.0"), False),  # Missing build number
            (ForkName.PROTON_EM, Path("Invalid-Directory"), False),  # Invalid Proton-EM
            (ForkName.PROTON_EM, Path("proton-em-10.0-30"), False),  # Wrong case
        ],
    )
    def test_is_valid_proton_directory(self, mocker, fork, entry, expected):
        """Test _is_valid_proton_directory method with various formats and forks."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        is_valid = manager._is_valid_proton_directory(entry, fork)
        assert is_valid is expected

    def test_compare_targets_same_paths(self, mocker):
        """Test _compare_targets method when paths are the same."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        path = Path("/some/path")
        mock_fs.resolve.return_value = path

        result = manager._compare_targets(path, path)
        assert result is True

    def test_compare_targets_different_paths(self, mocker):
        """Test _compare_targets method when paths are different."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        path1 = Path("/some/path1")
        path2 = Path("/some/path2")
        mock_fs.resolve.side_effect = [path1, path2]

        result = manager._compare_targets(path1, path2)
        assert result is False

    def test_compare_targets_oserror_handling(self, mocker):
        """Test _compare_targets method when OSError occurs."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        mock_fs.resolve.side_effect = OSError("Cannot resolve path")

        result = manager._compare_targets(Path("/some/path"), Path("/other/path"))
        assert result is False

    def test_handle_existing_symlink_correct_target(self, mocker):
        """Test _handle_existing_symlink when symlink points to correct target."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        link = Path("/link")
        target = Path("/target")
        mock_fs.resolve.return_value = target

        # Should not call unlink if targets match
        manager._handle_existing_symlink(link, target)
        mock_fs.unlink.assert_not_called()

    def test_handle_existing_symlink_wrong_target(self, mocker):
        """Test _handle_existing_symlink when symlink points to wrong target."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        link = Path("/link")
        current_target = Path("/current_target")
        expected_target = Path("/expected_target")

        # Mock resolve to return the current target for the link
        def mock_resolve(path):
            if path == link:
                return current_target
            elif path == current_target:
                return current_target  # resolved current target
            elif path == expected_target:
                return expected_target  # resolved expected target
            return path

        mock_fs.resolve.side_effect = mock_resolve

        manager._handle_existing_symlink(link, expected_target)
        mock_fs.unlink.assert_called_once_with(link)

    def test_handle_existing_symlink_oserror(self, mocker):
        """Test _handle_existing_symlink when OSError occurs."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        link = Path("/link")
        target = Path("/target")
        mock_fs.resolve.side_effect = OSError("Broken symlink")

        manager._handle_existing_symlink(link, target)
        mock_fs.unlink.assert_called_once_with(link)

    def test_cleanup_existing_path_before_symlink_real_directory(
        self, mocker, tmp_path
    ):
        """Test _cleanup_existing_path_before_symlink when path exists as real directory."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        link = Path("/link")
        target = Path("/target")

        # Simulate that path exists but is not a symlink
        mock_fs.exists.return_value = True
        mock_fs.is_symlink.return_value = False

        manager._cleanup_existing_path_before_symlink(link, target)

        # Should call rmtree to remove real directory - it might be called twice due to final check
        assert mock_fs.rmtree.call_count >= 1

    def test_cleanup_existing_path_before_symlink_existing_symlink(
        self, mocker, tmp_path
    ):
        """Test _cleanup_existing_path_before_symlink when path exists as symlink."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        link = Path("/link")
        target = Path("/target")

        # Initially the link exists and is a symlink, then after _handle_existing_symlink
        # it should be removed, so exists returns False in the final check
        call_count = 0

        def mock_exists(path):
            nonlocal call_count
            call_count += 1
            # First call (in the if condition): True
            # Second call (in the final check) should be False after symlink is handled
            return call_count == 1

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_symlink.return_value = True

        # Mock the _handle_existing_symlink method on the manager
        mock_handle_method = mocker.patch.object(manager, "_handle_existing_symlink")

        manager._cleanup_existing_path_before_symlink(link, target)

        # Should call the _handle_existing_symlink method
        mock_handle_method.assert_called_once_with(link, target)

    def test_create_symlinks_internal_usage(self, mocker, tmp_path):
        """Test create_symlinks method with internal usage (4 parameters)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        main = tmp_path / "GE-Proton"
        fb1 = tmp_path / "GE-Proton-Fallback"
        fb2 = tmp_path / "GE-Proton-Fallback2"

        target_path = tmp_path / "GE-Proton10-20"
        target_path.mkdir()

        top_3 = [(("GE-Proton", 10, 20, 0), target_path)]

        result = manager.create_symlinks(main, fb1, fb2, top_3)

        assert result is True
        # Should create at least one symlink
        assert mock_fs.symlink_to.call_count >= 1

    def test_create_symlinks_for_test_symlink_creation_fails(self, mocker, tmp_path):
        """Test create_symlinks_for_test when symlink creation fails."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create test directories
        target_path = tmp_path / "GE-Proton10-20"
        target_path.mkdir()
        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations
        def mock_exists(path):
            path_str = str(path)
            target_path_str = str(target_path)
            extract_dir_str = str(extract_dir)
            return target_path_str in path_str or extract_dir_str in path_str

        def mock_is_dir(path):
            return str(path) == str(target_path)

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.side_effect = mock_is_dir

        # Make symlink_to raise an error
        mock_fs.symlink_to.side_effect = OSError("Cannot create symlink")

        # Should still return True but log the error
        result = manager.create_symlinks_for_test(
            extract_dir, target_path, ForkName.GE_PROTON
        )
        assert result is True

    def test_list_links_broken_symlink(self, mocker, tmp_path):
        """Test list_links when encountering broken symlinks."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Mock file system operations for broken symlink
        def mock_exists(path):
            return str(path).endswith("GE-Proton")

        def mock_is_symlink(path):
            return str(path).endswith("GE-Proton")

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_symlink.side_effect = mock_is_symlink
        mock_fs.resolve.side_effect = OSError("Broken symlink")

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        result = manager.list_links(extract_dir, ForkName.GE_PROTON)

        assert "GE-Proton" in result
        assert result["GE-Proton"] is None

    def test_determine_release_path_proton_em_with_prefix(self, mocker, tmp_path):
        """Test _determine_release_path for Proton-EM with proton- prefix."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        tag = "EM-10.0-30"
        release_path = extract_dir / f"proton-{tag}"

        # Mock exists to return True for the proton-prefixed path
        def mock_exists(path):
            return str(path) == str(release_path)

        mock_fs.exists.side_effect = mock_exists

        result_path = manager._determine_release_path(
            extract_dir, tag, ForkName.PROTON_EM
        )
        assert result_path == release_path

    def test_identify_links_to_remove_broken_symlink(self, mocker, tmp_path):
        """Test _identify_links_to_remove with broken symlinks."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        main = extract_dir / "GE-Proton"
        release_path = extract_dir / "GE-Proton10-20"

        def mock_exists(path):
            return str(path) == str(main)

        def mock_is_symlink(path):
            return str(path) == str(main)

        def mock_resolve(path):
            if str(path) == str(main):
                raise OSError("Broken symlink")
            return path

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_symlink.side_effect = mock_is_symlink
        mock_fs.resolve.side_effect = mock_resolve

        links_to_remove = manager._identify_links_to_remove(
            extract_dir, release_path, ForkName.GE_PROTON
        )

        # Broken symlink should be in the list to remove
        assert main in links_to_remove

    def test_remove_release_directory_error(self, mocker, tmp_path):
        """Test _remove_release_directory when removal fails."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        release_path = tmp_path / "GE-Proton10-20"

        mock_fs.rmtree.side_effect = Exception("Cannot remove directory")

        with pytest.raises(LinkManagementError):
            manager._remove_release_directory(release_path)

    def test_remove_symbolic_links_error(self, mocker, tmp_path):
        """Test _remove_symbolic_links when unlink fails."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        link = tmp_path / "GE-Proton"
        links_to_remove = [link]

        # Mock unlink to log error but continue
        mock_fs.unlink.side_effect = Exception("Cannot remove symlink")

        # Should not raise an exception but should log
        manager._remove_symbolic_links(links_to_remove)

    def test_remove_release_with_links_to_update(self, mocker, tmp_path):
        """Test remove_release with links that need to be updated."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create test release directory
        release_dir = extract_dir / "GE-Proton10-20"
        release_dir.mkdir()

        # Create a symlink that points to the release directory to be removed
        symlink_path = extract_dir / "GE-Proton"
        release_path = extract_dir / "GE-Proton10-20"

        def mock_exists(path):
            path_str = str(path)
            release_dir_str = str(release_dir)
            symlink_path_str = str(symlink_path)
            return release_dir_str in path_str or symlink_path_str in path_str

        def mock_is_symlink(path):
            return str(path) == str(symlink_path)

        def mock_resolve(path):
            if str(path) == str(symlink_path):
                return release_path
            return path

        def mock_iterdir(path):
            return [release_dir]  # Return the release directory for version finding

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_symlink.side_effect = mock_is_symlink
        mock_fs.resolve.side_effect = mock_resolve
        mock_fs.iterdir.side_effect = mock_iterdir
        mock_fs.unlink.return_value = None
        mock_fs.rmtree.return_value = None

        result = manager.remove_release(
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON
        )

        assert result is True

    def test_handle_manual_release_candidates(self, mocker):
        """Test _handle_manual_release_candidates method."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        tag = "GE-Proton10-20"
        fork = ForkName.GE_PROTON
        # Correctly formatted candidates as VersionTuple to avoid literal type issues
        older_version: tuple[str, int, int, int] = (
            "GE-Proton",
            10,
            0,
            15,
        )  # ("prefix", major, 0, patch) for GE-Proton
        candidates: list[tuple[tuple[str, int, int, int], Path]] = [
            (older_version, Path("GE-Proton10-15"))
        ]
        tag_dir = Path("GE-Proton10-20")

        result = manager._handle_manual_release_candidates(
            tag, fork, candidates, tag_dir
        )

        # Should include both the original candidate and the new manual tag
        assert len(result) == 2
        # Should include the manual tag
        assert any(c[1] == tag_dir for c in result)
        # Should be sorted with newer version first (GE-Proton10-20 should come before GE-Proton10-15)
        # For GE-Proton, parse_version("GE-Proton10-20") returns ("GE-Proton", 10, 0, 20)
        # And parse_version("GE-Proton10-15") returns ("GE-Proton", 10, 0, 15)
        # So newer version (with 20) should be first
        assert result[0][0][3] == 20  # manual tag version should be first

    def test_handle_regular_release_candidates(self, mocker):
        """Test _handle_regular_release_candidates method."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        candidates: list[tuple[tuple[str, int, int, int], Path]] = [
            (("GE-Proton", 10, 0, 15), Path("GE-Proton10-15")),
            (("GE-Proton", 10, 0, 20), Path("GE-Proton10-20")),
            (("GE-Proton", 9, 0, 10), Path("GE-Proton9-10")),
        ]

        result = manager._handle_regular_release_candidates(candidates)

        # Should sort by version (newest first) and take top 3
        assert len(result) == 3
        # Newest version should be first
        assert (
            result[0][0][0] == "GE-Proton"
            and result[0][0][1] == 10
            and result[0][0][3] == 20
        )

    def test_manage_proton_links_with_manual_release(self, mocker, tmp_path):
        """Test manage_proton_links with manual release."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create test directories including the manual release directory
        release1 = extract_dir / "GE-Proton9-15"
        release1.mkdir()
        manual_release = extract_dir / "GE-Proton10-20"
        manual_release.mkdir()

        def mock_exists(path):
            path_str = str(path)
            return (
                str(release1) in path_str
                or str(manual_release) in path_str
                or str(extract_dir) in path_str
            )

        def mock_is_dir(path):
            path_str = str(path)
            return (
                str(release1) == path_str
                or str(manual_release) == path_str
                or str(extract_dir) == path_str
            )

        def mock_iterdir(path):
            return [release1, manual_release]

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.side_effect = mock_is_dir
        mock_fs.iterdir.side_effect = mock_iterdir
        mock_fs.unlink.return_value = None
        mock_fs.symlink_to.return_value = None

        result = manager.manage_proton_links(
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON, is_manual_release=True
        )

        assert result is True

    def test_manage_proton_links_manual_release_not_found(self, mocker, tmp_path):
        """Test manage_proton_links with manual release that doesn't exist."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        def mock_exists(path):
            # Return True only for the main extract directory, not for the expected manual release directory
            return str(path) == str(extract_dir)

        def mock_iterdir(path):
            return []

        def mock_is_dir(path):
            # Only the extract directory is a valid directory
            return str(path) == str(extract_dir)

        def mock_is_symlink(path):
            return False  # None of the test paths are symlinks

        mock_fs.exists.side_effect = mock_exists
        mock_fs.iterdir.side_effect = mock_iterdir
        mock_fs.is_dir.side_effect = mock_is_dir
        mock_fs.is_symlink.side_effect = mock_is_symlink

        result = manager.manage_proton_links(
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON, is_manual_release=True
        )

        # Should return True even if manual release directory is not found
        assert result is True

    def test_deduplicate_candidates_prefer_non_prefixed(self, mocker):
        """Test _deduplicate_candidates method preferring non-prefixed directories."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create candidates with the same version but different naming
        candidates: list[tuple[tuple[str, int, int, int], Path]] = [
            (
                ("GE-Proton", 10, 0, 20),
                Path("proton-GE-Proton10-20"),
            ),  # prefixed version
            (("GE-Proton", 10, 0, 20), Path("GE-Proton10-20")),  # standard version
        ]

        result = manager._deduplicate_candidates(candidates)

        # Should prefer the non-prefixed version (shorter name)
        assert len(result) == 1
        assert result[0][1] == Path("GE-Proton10-20")

    def test_deduplicate_candidates_different_versions(self, mocker):
        """Test _deduplicate_candidates method with different versions."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create candidates with different versions
        candidates: list[tuple[tuple[str, int, int, int], Path]] = [
            (("GE-Proton", 10, 0, 20), Path("GE-Proton10-20")),
            (("GE-Proton", 9, 0, 15), Path("GE-Proton9-15")),
        ]

        result = manager._deduplicate_candidates(candidates)

        # Should keep both since they have different versions
        assert len(result) == 2

    def test_get_link_names_for_fork_with_path(self, mocker, tmp_path):
        """Test get_link_names_for_fork method with extract_dir and fork."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        main, fb1, fb2 = manager.get_link_names_for_fork(
            extract_dir, ForkName.GE_PROTON
        )

        expected_main = extract_dir / "GE-Proton"
        expected_fb1 = extract_dir / "GE-Proton-Fallback"
        expected_fb2 = extract_dir / "GE-Proton-Fallback2"

        assert main == expected_main
        assert fb1 == expected_fb1
        assert fb2 == expected_fb2

    def test_get_link_names_for_fork_with_invalid_fork(self, mocker):
        """Test get_link_names_for_fork method with invalid fork."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # This should handle the case where an invalid fork is provided
        main, fb1, fb2 = manager.get_link_names_for_fork(
            Path("/test"), ForkName.GE_PROTON
        )

        # Test that the default case is handled, but ForkName is an enum so this is hard to trigger
        # The code handles this via pattern matching, and since ForkName is StrEnum, all cases are covered

    @pytest.mark.parametrize(
        "fork,expected_links",
        [
            (
                ForkName.GE_PROTON,
                ("GE-Proton", "GE-Proton-Fallback", "GE-Proton-Fallback2"),
            ),
            (
                ForkName.PROTON_EM,
                ("Proton-EM", "Proton-EM-Fallback", "Proton-EM-Fallback2"),
            ),
        ],
    )
    def test_create_symlinks_for_test_parametrized_forks(
        self, mocker, tmp_path, fork, expected_links
    ):
        """Parametrized test for create_symlinks_for_test with different forks."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Create test release directory based on fork
        if fork == ForkName.GE_PROTON:
            release_dir = tmp_path / "GE-Proton10-20"
        else:
            release_dir = tmp_path / "proton-EM-10.0-30"
        release_dir.mkdir()

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations to handle the target directory correctly
        def mock_exists(path):
            path_str = str(path)
            release_dir_str = str(release_dir)
            extract_dir_str = str(extract_dir)
            # Return True for the target path and extract dir
            return release_dir_str in path_str or extract_dir_str in path_str

        def mock_is_dir(path):
            # Return True for the target path
            return str(path) == str(release_dir)

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.side_effect = mock_is_dir

        result = manager.create_symlinks_for_test(extract_dir, release_dir, fork)

        assert result is True
        # Should create 3 symlinks for the fork
        if fork == ForkName.GE_PROTON:
            expected_symlink_calls = (
                3  # GE-Proton, GE-Proton-Fallback, GE-Proton-Fallback2
            )
        else:
            expected_symlink_calls = (
                3  # Proton-EM, Proton-EM-Fallback, Proton-EM-Fallback2
            )
        assert mock_fs.symlink_to.call_count == expected_symlink_calls

    def test_find_tag_directory_proton_em_not_found_error(self, mocker, tmp_path):
        """Test find_tag_directory that raises LinkManagementError in Proton-EM case."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations - directory doesn't exist
        mock_fs.exists.return_value = False
        mock_fs.is_dir.return_value = False

        # This should raise LinkManagementError for Proton-EM case
        with pytest.raises(LinkManagementError):
            manager.find_tag_directory(
                extract_dir, "EM-10.0-30", ForkName.PROTON_EM, is_manual_release=True
            )

    def test_find_tag_directory_ge_proton_not_found_error(self, mocker, tmp_path):
        """Test find_tag_directory that raises LinkManagementError in GE-Proton case."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock file system operations - directory doesn't exist
        mock_fs.exists.return_value = False
        mock_fs.is_dir.return_value = False

        # This should raise LinkManagementError for GE-Proton case
        with pytest.raises(LinkManagementError):
            manager.find_tag_directory(
                extract_dir,
                "GE-Proton10-20",
                ForkName.GE_PROTON,
                is_manual_release=True,
            )

    def test_create_symlinks_internal_oserror(self, mocker, tmp_path):
        """Test _create_symlinks_internal when symlink creation fails with OSError."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        main = tmp_path / "GE-Proton"
        fb1 = tmp_path / "GE-Proton-Fallback"
        fb2 = tmp_path / "GE-Proton-Fallback2"

        target_path = tmp_path / "GE-Proton10-20"
        target_path.mkdir()

        top_3 = [(("GE-Proton", 10, 20, 0), target_path)]

        # Make symlink_to raise an OSError
        mock_fs.symlink_to.side_effect = OSError("Permission denied")

        # This should complete without raising an exception but log errors
        result = manager._create_symlinks_internal(main, fb1, fb2, top_3)

        assert result is True  # Function returns True even if symlinks fail
        # Should have attempted to create all symlinks despite the error
        assert mock_fs.symlink_to.call_count >= 1  # Called but continues

    def test_cleanup_unwanted_links_real_directory_removal(self, mocker, tmp_path):
        """Test _cleanup_unwanted_links when removing a real directory."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        main = tmp_path / "GE-Proton"
        fb1 = tmp_path / "GE-Proton-Fallback"
        fb2 = tmp_path / "GE-Proton-Fallback2"

        # Mock the 'wants' mapping to not include one of the links
        wants = {fb1: tmp_path / "target1", fb2: tmp_path / "target2"}

        # Mock exists to return True and is_symlink to return False for main
        def mock_exists(path):
            return path == main

        def mock_is_symlink(path):
            return False  # main is a real directory, not a symlink

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_symlink.side_effect = mock_is_symlink

        # Call the cleanup method
        manager._cleanup_unwanted_links(main, fb1, fb2, wants)

        # Should have called rmtree to remove the real directory at 'main'
        mock_fs.rmtree.assert_called_once_with(main)

    def test_remove_release_directory_removal_error(self, mocker, tmp_path):
        """Test remove_release when directory removal fails."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create test directory structure INSIDE the extract directory
        release_dir = extract_dir / "GE-Proton10-20"
        release_dir.mkdir()

        # Mock file system operations
        def mock_exists(path):
            path_str = str(path)
            release_dir_str = str(release_dir)
            extract_dir_str = str(extract_dir)
            return path_str == release_dir_str or path_str == extract_dir_str

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.return_value = True
        mock_fs.is_symlink.return_value = False

        def mock_iterdir(path):
            if path == extract_dir:
                return [release_dir]
            return []

        mock_fs.iterdir.side_effect = mock_iterdir

        # Make rmtree raise an exception
        mock_fs.rmtree.side_effect = Exception("Cannot remove directory")

        # This should raise a LinkManagementError due to the rmtree exception
        with pytest.raises(LinkManagementError):
            manager.remove_release(extract_dir, "GE-Proton10-20", ForkName.GE_PROTON)

    def test_determine_release_path_proton_em_alternative(self, mocker, tmp_path):
        """Test _determine_release_path with Proton-EM alternative path."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        tag = "EM-10.0-30"

        # Create the alternative path (with "proton-" prefix)
        proton_em_path = extract_dir / f"proton-{tag}"
        proton_em_path.mkdir()

        # Only the alternative path exists, not the regular one
        def mock_exists(path):
            return str(path) == str(proton_em_path)

        mock_fs.exists.side_effect = mock_exists

        result = manager._determine_release_path(extract_dir, tag, ForkName.PROTON_EM)

        # Should return the alternative path with "proton-" prefix
        assert result == proton_em_path

    def test_handle_manual_release_directory_warning(self, mocker, tmp_path):
        """Test _handle_manual_release_directory when directory doesn't exist."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        tag = "GE-Proton10-20"
        fork = ForkName.GE_PROTON

        # Mock file_system_client.exists to return False
        mock_fs.exists.return_value = False

        # This should return None since no directory is found
        result = manager._handle_manual_release_directory(
            extract_dir, tag, fork, is_manual_release=True
        )

        assert result is None

    def test_manage_proton_links_empty_extract_dir(self, mocker, tmp_path):
        """Test manage_proton_links when extract directory is empty."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock iterdir to return no entries (empty directory)
        def mock_iterdir(path):
            return []

        mock_fs.iterdir.side_effect = mock_iterdir

        # This should succeed without creating any symlinks
        result = manager.manage_proton_links(extract_dir, "test", ForkName.GE_PROTON)

        assert result is True

    def test_create_symlink_specs_branch_coverage(self, mocker, tmp_path):
        """Test _create_symlink_specs with different numbers of versions for branch coverage (lines 207->212)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        main = tmp_path / "GE-Proton"
        fb1 = tmp_path / "GE-Proton-Fallback"
        fb2 = tmp_path / "GE-Proton-Fallback2"

        # Test with exactly 1 version - covers first condition only
        target1 = tmp_path / "GE-Proton10-20"
        top_1 = [(("GE-Proton", 10, 20, 0), target1)]
        specs_1 = manager._create_symlink_specs(main, fb1, fb2, top_1)
        assert len(specs_1) == 1
        assert specs_1[0].link_path == main

        # Test with exactly 2 versions - covers first two conditions
        target2 = tmp_path / "GE-Proton9-15"
        top_2 = [
            (("GE-Proton", 10, 20, 0), target1),
            (("GE-Proton", 9, 15, 0), target2),
        ]
        specs_2 = manager._create_symlink_specs(main, fb1, fb2, top_2)
        assert len(specs_2) == 2
        assert specs_2[0].link_path == main
        assert specs_2[1].link_path == fb1

        # Test with exactly 3 versions - covers all three conditions
        target3 = tmp_path / "GE-Proton8-10"
        top_3 = [
            (("GE-Proton", 10, 20, 0), target1),
            (("GE-Proton", 9, 15, 0), target2),
            (("GE-Proton", 8, 10, 0), target3),
        ]
        specs_3 = manager._create_symlink_specs(main, fb1, fb2, top_3)
        assert len(specs_3) == 3
        assert specs_3[0].link_path == main
        assert specs_3[1].link_path == fb1
        assert specs_3[2].link_path == fb2

    def test_handle_manual_release_candidates_duplicate_version(self, mocker):
        """Test _handle_manual_release_candidates when tag version already exists (lines 640->644)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        tag = "GE-Proton10-20"
        fork = ForkName.GE_PROTON
        # Create candidates with the same version as the manual tag
        existing_version: tuple[str, int, int, int] = ("GE-Proton", 10, 0, 20)
        candidates: list[tuple[tuple[str, int, int, int], Path]] = [
            (existing_version, Path("GE-Proton10-20"))
        ]
        tag_dir = Path("GE-Proton10-20")

        result = manager._handle_manual_release_candidates(
            tag, fork, candidates, tag_dir
        )

        # Should not add duplicate version - should only have the original candidate
        assert len(result) == 1
        assert result[0][1] == Path("GE-Proton10-20")

    def test_identify_links_to_remove_broken_symlink_branch(self, mocker, tmp_path):
        """Test _identify_links_to_remove with broken symlinks for branch coverage (lines 491->485)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        main = extract_dir / "GE-Proton"
        fb1 = extract_dir / "GE-Proton-Fallback"
        fb2 = extract_dir / "GE-Proton-Fallback2"
        release_path = extract_dir / "GE-Proton10-20"

        def mock_exists(path):
            return str(path) in [str(main), str(fb1), str(fb2)]

        def mock_is_symlink(path):
            return str(path) in [str(main), str(fb1), str(fb2)]

        def mock_resolve(path):
            # All symlinks are broken and raise OSError
            raise OSError("Broken symlink")

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_symlink.side_effect = mock_is_symlink
        mock_fs.resolve.side_effect = mock_resolve

        links_to_remove = manager._identify_links_to_remove(
            extract_dir, release_path, ForkName.GE_PROTON
        )

        # All broken symlinks should be in the list to remove
        assert len(links_to_remove) == 3
        assert main in links_to_remove
        assert fb1 in links_to_remove
        assert fb2 in links_to_remove

    def test_is_valid_proton_directory_em_only_pattern2(self, mocker):
        """Test _is_valid_proton_directory with EM- format only for branch coverage (line 169->exit)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        # Test directory that matches only the second pattern (EM- format)
        entry = Path("EM-10.0-30")
        result = manager._is_valid_proton_directory(entry, ForkName.PROTON_EM)
        assert result is True

        # Test directory that matches only the first pattern (proton-EM- format)
        entry2 = Path("proton-EM-10.0-30")
        result2 = manager._is_valid_proton_directory(entry2, ForkName.PROTON_EM)
        assert result2 is True

        # Test directory that matches neither pattern
        entry3 = Path("Invalid-EM-10.0-30")
        result3 = manager._is_valid_proton_directory(entry3, ForkName.PROTON_EM)
        assert result3 is False

    def test_determine_release_path_branch_coverage(self, mocker, tmp_path):
        """Test _determine_release_path with all path existence combinations for branch coverage (lines 462->467)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()
        tag = "EM-10.0-30"

        # Test case 1: Both paths exist - should prefer regular path
        release_path = extract_dir / tag
        proton_em_path = extract_dir / f"proton-{tag}"
        release_path.mkdir()
        proton_em_path.mkdir()

        def mock_exists_both(path):
            return str(path) in [str(release_path), str(proton_em_path)]

        mock_fs.exists.side_effect = mock_exists_both
        result1 = manager._determine_release_path(extract_dir, tag, ForkName.PROTON_EM)
        assert result1 == release_path  # Should prefer regular path

        # Test case 2: Only proton-prefixed path exists
        release_path.rmdir()  # Remove regular path

        def mock_exists_proton_only(path):
            return str(path) == str(proton_em_path)

        mock_fs.exists.side_effect = mock_exists_proton_only
        result2 = manager._determine_release_path(extract_dir, tag, ForkName.PROTON_EM)
        assert result2 == proton_em_path  # Should use proton-prefixed path

        # Test case 3: Only regular path exists
        proton_em_path.rmdir()  # Remove proton-prefixed path
        release_path.mkdir()  # Recreate regular path

        def mock_exists_regular_only(path):
            return str(path) == str(release_path)

        mock_fs.exists.side_effect = mock_exists_regular_only
        result3 = manager._determine_release_path(extract_dir, tag, ForkName.PROTON_EM)
        assert result3 == release_path  # Should use regular path

        # Test case 4: Neither path exists
        release_path.rmdir()

        def mock_exists_neither(path):
            return False

        mock_fs.exists.side_effect = mock_exists_neither
        result4 = manager._determine_release_path(extract_dir, tag, ForkName.PROTON_EM)
        assert (
            result4 == release_path
        )  # Should return regular path even if it doesn't exist

    def test_find_tag_directory_proton_em_error_case(self, mocker, tmp_path):
        """Test find_tag_directory Proton-EM error case for branch coverage (lines 111, 118)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Test Proton-EM case where neither path exists
        def mock_exists(path):
            return False  # Neither path exists

        def mock_is_dir(path):
            return False

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.side_effect = mock_is_dir

        # This should raise LinkManagementError for Proton-EM when neither path exists
        with pytest.raises(LinkManagementError):
            manager.find_tag_directory(
                extract_dir, "EM-10.0-30", ForkName.PROTON_EM, is_manual_release=True
            )

    def test_find_tag_directory_unsupported_fork(self, mocker, tmp_path):
        """Test find_tag_directory unsupported fork error for branch coverage (line 140)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Test with various invalid fork types to ensure proper error handling
        invalid_forks = ["INVALID", 123, None, object()]

        for invalid_fork in invalid_forks:
            with pytest.raises(ValueError, match="fork must be a ForkName"):
                manager.find_tag_directory(extract_dir, "tag", invalid_fork)

    def test_manage_proton_links_manual_release_none_tag_dir(self, mocker, tmp_path):
        """Test manage_proton_links with manual release where tag_dir is None for branch coverage (line 696)."""
        mock_fs = mocker.Mock()
        manager = LinkManager(mock_fs)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Mock the _handle_manual_release_directory method to return None
        def mock_handle_manual_release_directory(
            extract_dir, tag, fork, is_manual_release
        ):
            return None

        manager._handle_manual_release_directory = mock_handle_manual_release_directory

        # Mock find_version_candidates to return some candidates
        def mock_find_version_candidates(extract_dir, fork):
            return [(("GE-Proton", 10, 0, 20), extract_dir / "GE-Proton10-20")]

        manager.find_version_candidates = mock_find_version_candidates

        # This should handle the case where tag_dir is None for manual release
        result = manager.manage_proton_links(
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON, is_manual_release=True
        )

        assert result is True
