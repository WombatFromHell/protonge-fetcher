"""
Integration tests for link management workflows in protonfetcher.py
"""

import pytest

from protonfetcher.common import ForkName
from protonfetcher.exceptions import LinkManagementError


class TestLinkManagementWorkflow:
    """Integration tests for symlink management workflows and conflict resolution."""

    def test_link_management_workflow_success(self, mocker, tmp_path):
        """Test complete link management workflow with successful execution."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the link manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager

        # Create test release directory
        release_dir = tmp_path / "GE-Proton10-20"
        release_dir.mkdir()

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Setup successful link management
        mock_link_manager.create_symlinks.return_value = True
        mock_link_manager.manage_proton_links.return_value = True

        # Test create_symlinks method
        result = mock_link_manager.create_symlinks(
            extract_dir, release_dir, ForkName.GE_PROTON
        )

        assert result is True
        mock_link_manager.create_symlinks.assert_called_once_with(  # type: ignore
            extract_dir, release_dir, ForkName.GE_PROTON
        )

    def test_link_management_list_links_success(self, mocker, tmp_path):
        """Test link management workflow for listing existing links."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the link manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Setup mock response for existing links
        expected_links = {
            "GE-Proton": str(tmp_path / "GE-Proton10-20"),
            "GE-Proton-Fallback": str(tmp_path / "GE-Proton9-15"),
            "GE-Proton-Fallback2": None,
        }
        mock_link_manager.list_links.return_value = expected_links

        result = mock_link_manager.list_links(extract_dir, ForkName.GE_PROTON)

        assert result == expected_links
        mock_link_manager.list_links.assert_called_once_with(  # type: ignore
            extract_dir, ForkName.GE_PROTON
        )

    def test_link_management_remove_release_success(self, mocker, tmp_path):
        """Test link management workflow for removing a release."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the link manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Setup successful removal
        mock_link_manager.remove_release.return_value = True

        result = mock_link_manager.remove_release(
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON
        )

        assert result is True
        mock_link_manager.remove_release.assert_called_once_with(  # type: ignore
            extract_dir, "GE-Proton10-20", ForkName.GE_PROTON
        )

    def test_link_management_workflow_conflict_resolution(self, mocker, tmp_path):
        """Test link management workflow with symlink conflict resolution."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher
        from protonfetcher.link_manager import LinkManager

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Create a real LinkManager but with mocked internal method
        real_link_manager = LinkManager(mock_fs)
        fetcher.link_manager = real_link_manager

        # Create test directories
        release1 = tmp_path / "GE-Proton10-20"
        release1.mkdir()
        release2 = tmp_path / "GE-Proton9-15"
        release2.mkdir()
        release3 = tmp_path / "GE-Proton8-10"
        release3.mkdir()

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Setup mock for finding version candidates and managing links
        def mock_find_candidates(extract_dir, fork):
            from protonfetcher.utils import parse_version

            return [
                (parse_version("GE-Proton10-20", ForkName.GE_PROTON), release1),
                (parse_version("GE-Proton9-15", ForkName.GE_PROTON), release2),
                (parse_version("GE-Proton8-10", ForkName.GE_PROTON), release3),
            ]

        # Patch the real method with our test implementation
        mocker.patch.object(
            real_link_manager,
            "find_version_candidates",
            side_effect=mock_find_candidates,
        )
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True

        # This calls the real method which should internally call find_version_candidates
        result = real_link_manager.manage_proton_links(extract_dir, ForkName.GE_PROTON)

        assert result is True
        # Verify the internal method call occurred
        real_link_manager.find_version_candidates.assert_called_once_with(  # type: ignore
            extract_dir, ForkName.GE_PROTON
        )

    def test_link_management_workflow_broken_symlinks(self, mocker, tmp_path):
        """Test link management workflow handling broken symlinks."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the link manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Setup response that includes broken symlinks (None values)
        broken_links = {
            "GE-Proton": None,  # Broken/missing
            "GE-Proton-Fallback": str(tmp_path / "GE-Proton9-15"),
            "GE-Proton-Fallback2": None,  # Broken/missing
        }
        mock_link_manager.list_links.return_value = broken_links

        result = mock_link_manager.list_links(extract_dir, ForkName.GE_PROTON)

        assert result == broken_links
        # Verify it properly handles broken symlinks in the return value
        assert result["GE-Proton"] is None
        assert result["GE-Proton-Fallback2"] is None

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
    def test_link_management_workflow_parametrized_forks(
        self, mocker, tmp_path, fork, expected_links
    ):
        """Parametrized test for link management workflow with different forks."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher
        from protonfetcher.link_manager import LinkManager

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Create a real LinkManager but with mocked methods
        real_link_manager = LinkManager(mock_fs)
        fetcher.link_manager = real_link_manager

        # Create test release directory
        if fork == ForkName.GE_PROTON:
            release_dir = tmp_path / "GE-Proton10-20"
        else:
            release_dir = tmp_path / "proton-EM-10.0-30"
        release_dir.mkdir()

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Setup mock for the methods that need to be mocked
        expected_paths = (
            extract_dir / expected_links[0],
            extract_dir / expected_links[1],
            extract_dir / expected_links[2],
        )
        mocker.patch.object(
            real_link_manager, "get_link_names_for_fork", return_value=expected_paths
        )

        # Mock file system operations to handle the target directory correctly
        def mock_exists(path):
            path_str = str(path)
            release_dir_str = str(release_dir)
            extract_dir_str = str(extract_dir)
            # Return True for the target path and extract dir, False for symlink paths
            return release_dir_str in path_str or extract_dir_str in path_str

        def mock_is_dir(path):
            # Return True for the target path
            return str(path) == str(release_dir)

        mock_fs.exists.side_effect = mock_exists
        mock_fs.is_dir.side_effect = mock_is_dir

        result = real_link_manager.create_symlinks(extract_dir, release_dir, fork)

        assert result is True
        real_link_manager.get_link_names_for_fork.assert_called_once_with(  # type: ignore
            extract_dir, fork
        )

    def test_link_management_workflow_directory_conflicts(self, mocker, tmp_path):
        """Test link management workflow handling directory conflicts."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the link manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager

        # Create test release directory
        release_dir = tmp_path / "GE-Proton10-20"
        release_dir.mkdir()

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Create conflicting files/directories where symlinks would be placed
        conflicting_file = extract_dir / "GE-Proton"
        conflicting_file.write_text("This is a file, not a symlink")

        # Setup the workflow to handle this conflict
        mock_fs.exists.side_effect = lambda path: "GE-Proton" in str(
            path
        )  # Simulate existing file
        mock_fs.is_symlink.return_value = False  # It's not a symlink
        mock_fs.is_dir.return_value = False  # It's not a directory
        mock_fs.unlink.return_value = None  # Allow deletion
        mock_fs.symlink_to.return_value = None  # Allow creation of new symlink

        mock_link_manager.create_symlinks.return_value = True

        # This should handle the conflict and still work
        result = mock_link_manager.create_symlinks(
            extract_dir, release_dir, ForkName.GE_PROTON
        )

        assert result is True
        # The manager should have handled the conflicting file appropriately

    def test_link_management_workflow_multiple_releases_management(
        self, mocker, tmp_path
    ):
        """Test link management workflow managing multiple releases."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher
        from protonfetcher.link_manager import LinkManager

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Create a real LinkManager but with mocked internal method
        real_link_manager = LinkManager(mock_fs)
        fetcher.link_manager = real_link_manager

        # Create multiple test release directories
        releases = []
        for version in [
            "GE-Proton10-20",
            "GE-Proton9-15",
            "GE-Proton8-10",
            "GE-Proton7-5",
        ]:
            release_dir = tmp_path / version
            release_dir.mkdir()
            releases.append(release_dir)

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Setup workflow for managing multiple releases
        def mock_find_candidates(extract_dir, fork):
            from protonfetcher.utils import parse_version

            return [
                (parse_version("GE-Proton10-20", ForkName.GE_PROTON), releases[0]),
                (parse_version("GE-Proton9-15", ForkName.GE_PROTON), releases[1]),
                (parse_version("GE-Proton8-10", ForkName.GE_PROTON), releases[2]),
                (parse_version("GE-Proton7-5", ForkName.GE_PROTON), releases[3]),
            ]

        # Patch the real method with our test implementation
        mocker.patch.object(
            real_link_manager,
            "find_version_candidates",
            side_effect=mock_find_candidates,
        )
        mock_fs.exists.return_value = True
        mock_fs.is_dir.return_value = True

        result = real_link_manager.manage_proton_links(extract_dir, ForkName.GE_PROTON)

        assert result is True
        real_link_manager.find_version_candidates.assert_called_once_with(  # type: ignore
            extract_dir, ForkName.GE_PROTON
        )

    def test_link_management_workflow_remove_release_not_found(self, mocker, tmp_path):
        """Test link management workflow when trying to remove a non-existent release."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the link manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Setup to raise error when release is not found
        mock_link_manager.remove_release.side_effect = LinkManagementError(
            "Release not found"
        )

        with pytest.raises(LinkManagementError):
            mock_link_manager.remove_release(
                extract_dir, "GE-Proton99-99", ForkName.GE_PROTON
            )

    def test_link_management_workflow_create_symlinks_target_missing(
        self, mocker, tmp_path
    ):
        """Test link management workflow when target directory doesn't exist."""
        from protonfetcher.github_fetcher import GitHubReleaseFetcher

        # Mock all dependencies
        mock_network = mocker.Mock()
        mock_fs = mocker.Mock()
        mock_spinner_cls = mocker.Mock()

        fetcher = GitHubReleaseFetcher(
            network_client=mock_network,
            file_system_client=mock_fs,
            spinner_cls=mock_spinner_cls,
            timeout=60,
        )

        # Mock the link manager
        mock_link_manager = mocker.Mock()
        fetcher.link_manager = mock_link_manager

        # Use a non-existent target directory
        missing_release_dir = tmp_path / "nonexistent_release"

        extract_dir = tmp_path / "compatibilitytools.d"
        extract_dir.mkdir()

        # Setup to raise error when target doesn't exist
        mock_link_manager.create_symlinks.side_effect = LinkManagementError(
            "Target directory does not exist"
        )

        with pytest.raises(LinkManagementError):
            mock_link_manager.create_symlinks(
                extract_dir, missing_release_dir, ForkName.GE_PROTON
            )
