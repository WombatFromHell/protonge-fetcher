"""Link manager implementation for ProtonFetcher."""

import logging
from pathlib import Path

from .candidate_selection import select_top_3_candidates as _select_top_3
from .common import (
    DEFAULT_TIMEOUT,
    FORKS,
    FileSystemClientProtocol,
    ForkName,
    VersionCandidateList,
)
from .dirs import get_link_names, resolve_directory
from .exceptions import LinkManagementError
from .link_status import (
    build_expected_link_mapping as _build_expected_link_mapping,
)
from .link_status import (
    compare_link_targets as _compare_link_targets,
)
from .link_status import (
    has_managed_links as _has_managed_links,
)
from .link_status import (
    get_installed_versions as _get_installed,
    get_linked_versions as _get_linked,
    list_links as _list_links,
)
from .prune_operations import prune_releases as _prune_releases
from .release_operations import remove_release as _remove_release
from .symlink_operations import create_symlinks as _create_symlinks
from .version_finder import _deduplicate_candidates, find_version_candidates

logger = logging.getLogger(__name__)


class LinkManager:
    """Manages symbolic links for Proton installations."""

    def __init__(
        self,
        file_system_client: FileSystemClientProtocol,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.file_system_client = file_system_client
        self.timeout = timeout

    def find_tag_directory(
        self,
        extract_dir: Path,
        tag: str,
        fork: ForkName,
        is_manual_release: bool = True,
    ) -> Path | None:
        """Find the tag directory for manual releases.

        Args:
            extract_dir: Directory to search for the tag directory
            tag: The release tag to find
            fork: The Proton fork name
            is_manual_release: Whether this is a manual release (default: True)

        Returns:
            Path to the found directory, or None if not found

        Raises:
            LinkManagementError: If manual release directory is not found when expected
            ValueError: If fork is not supported
        """
        if not is_manual_release:
            return None
        if fork not in FORKS:
            raise ValueError(f"Unsupported fork: {fork}")
        return resolve_directory(extract_dir, tag, fork, self.file_system_client)

    def find_version_candidates(
        self, extract_dir: Path, fork: ForkName
    ) -> VersionCandidateList:
        """Find all directories that look like Proton builds and parse their versions.

        Delegates to the version_finder submodule.
        """
        return find_version_candidates(extract_dir, fork, self.file_system_client)

    def create_symlinks(
        self, main: Path, fb1: Path, fb2: Path, top_3: VersionCandidateList
    ) -> bool:
        """Create symlinks for internal usage.

        Args:
            main: Main symlink path
            fb1: First fallback symlink path
            fb2: Second fallback symlink path
            top_3: List of top 3 version candidates to link to

        Returns:
            True if symlink creation was attempted (even if some failed)
        """
        return _create_symlinks(main, fb1, fb2, top_3, self.file_system_client)

    def list_links(
        self, extract_dir: Path, fork: ForkName = ForkName.GE_PROTON
    ) -> dict[str, str | None]:
        """List recognized symbolic links and their associated Proton fork folders.

        Delegates to the link_status submodule.

        Args:
            extract_dir: Directory to search for links
            fork: The Proton fork name to determine link naming

        Returns:
            Dictionary mapping link names to their target paths (or None if link doesn't exist)
        """
        return _list_links(extract_dir, fork, self.file_system_client)

    def has_managed_links(
        self, extract_dir: Path, fork: ForkName = ForkName.GE_PROTON
    ) -> bool:
        """Check if a fork has any managed symbolic links.

        Delegates to the link_status submodule.

        Args:
            extract_dir: Directory to search for links
            fork: The Proton fork name to determine link naming

        Returns:
            True if at least one managed symlink exists for the fork, False otherwise
        """
        return _has_managed_links(extract_dir, fork, self.file_system_client)

    def deduplicate_candidates(
        self, candidates: VersionCandidateList
    ) -> VersionCandidateList:
        """Remove duplicate versions, preferring standard naming.

        Delegates to the version_finder submodule.
        """
        return _deduplicate_candidates(candidates)

    def remove_release(
        self, extract_dir: Path, tag: str, fork: ForkName = ForkName.GE_PROTON
    ) -> bool:
        """Remove a specific Proton fork release folder and its associated symlinks.

        Delegates to the release_operations submodule.

        Args:
            extract_dir: Directory containing the release folder
            tag: The release tag to remove
            fork: The Proton fork name to determine link naming

        Returns:
            True if the removal was successful, False otherwise
        """
        _remove_release(extract_dir, tag, fork, self.file_system_client)
        # Regenerate the link management system to ensure consistency
        self.manage_proton_links(extract_dir, tag, fork)
        return True

    def _get_expected_manual_release_path(
        self, extract_dir: Path, tag: str, fork: ForkName
    ) -> Path:
        """Get the expected path for a manual release directory.

        Derived from the fork's primary directory-name template so it stays
        in sync with extraction naming (single source of truth).

        Args:
            extract_dir: Base extraction directory
            tag: Release tag
            fork: Proton fork name

        Returns:
            Expected path for the manual release directory
        """
        template = FORKS[fork].dir_name_templates[0]
        return extract_dir / template.format(tag=tag)

    def _log_manual_release_warning(self, expected_path: Path) -> None:
        """Log a warning when expected manual release directory is not found."""
        logger.warning("Expected extracted directory does not exist: %s", expected_path)

    def _handle_manual_release_directory(
        self, extract_dir: Path, tag: str, fork: ForkName, is_manual_release: bool
    ) -> Path | None:
        """Handle manual release by finding the tag directory.

        Args:
            extract_dir: Directory to search for the tag directory
            tag: The release tag to find
            fork: The Proton fork name
            is_manual_release: Whether this is a manual release

        Returns:
            Path to the found directory, or None if not found
        """
        if not is_manual_release:
            return self.find_tag_directory(extract_dir, tag, fork, is_manual_release)

        try:
            tag_dir = self.find_tag_directory(extract_dir, tag, fork, is_manual_release)
        except LinkManagementError:
            expected_path = self._get_expected_manual_release_path(
                extract_dir, tag, fork
            )
            self._log_manual_release_warning(expected_path)
            return None

        if tag_dir is None:
            expected_path = self._get_expected_manual_release_path(
                extract_dir, tag, fork
            )
            self._log_manual_release_warning(expected_path)
            return None

        return tag_dir

    def are_links_up_to_date(
        self,
        extract_dir: Path,
        tag: str,
        fork: ForkName = ForkName.GE_PROTON,
        is_manual_release: bool = False,
    ) -> bool:
        """Check if existing symlinks are already correct and up-to-date.

        Orchestrates: manual release check → candidate selection → link comparison.

        Args:
            extract_dir: Directory containing the Proton installations
            tag: The release tag being processed
            fork: The Proton fork name
            is_manual_release: Whether this is a manual release

        Returns:
            True if links are already correct, False if they need updating
        """
        main, fb1, fb2 = get_link_names(extract_dir, fork)
        link_names = (main, fb1, fb2)

        tag_dir = self._handle_manual_release_directory(
            extract_dir, tag, fork, is_manual_release
        )

        if is_manual_release and tag_dir is None:
            return False

        top_3 = _select_top_3(extract_dir, fork, tag_dir, self.file_system_client)
        if top_3 is None:
            return False

        current_links = self.list_links(extract_dir, fork)
        expected_links = _build_expected_link_mapping(link_names, top_3)

        return _compare_link_targets(current_links, expected_links)

    def manage_proton_links(
        self,
        extract_dir: Path,
        tag: str,
        fork: ForkName = ForkName.GE_PROTON,
        is_manual_release: bool = False,
    ) -> bool:
        """Ensure the three symlinks always point to the three newest extracted versions.

        Orchestrates: manual release check → candidate selection → symlink creation.

        Returns:
            True if the operation was successful
        """
        main, fb1, fb2 = get_link_names(extract_dir, fork)

        tag_dir = self._handle_manual_release_directory(
            extract_dir, tag, fork, is_manual_release
        )

        if is_manual_release and tag_dir is None:
            return True

        top_3 = _select_top_3(extract_dir, fork, tag_dir, self.file_system_client)
        if top_3 is None:
            logger.warning("No extracted Proton directories found – not touching links")
            return True

        self.create_symlinks(main, fb1, fb2, top_3)
        return True

    def get_installed_versions(self, extract_dir: Path, fork: ForkName) -> list[str]:
        """Get list of currently installed version tags for a fork.

        Args:
            extract_dir: Directory to search for installed versions
            fork: The Proton fork name

        Returns:
            List of version tag strings, sorted newest first
        """
        return _get_installed(extract_dir, fork, self.file_system_client)

    def get_linked_versions(self, extract_dir: Path, fork: ForkName) -> set[str]:
        """Get set of version directories currently referenced by symlinks.

        Args:
            extract_dir: Directory to search for symlinks
            fork: The Proton fork name

        Returns:
            Set of directory names currently linked
        """
        return _get_linked(extract_dir, fork, self.file_system_client)

    def _compute_prune_plan(
        self, extract_dir: Path, fork: ForkName, keep: int
    ) -> tuple[list[str], list[str]]:
        """Compute which versions to keep and which to prune.

        Delegates to the prune_operations submodule.

        Returns:
            Tuple of (kept_versions, pruned_versions) lists
        """
        from .prune_operations import compute_prune_plan as _compute

        return _compute(extract_dir, fork, keep, self.file_system_client)

    def prune_releases(
        self,
        extract_dir: Path,
        fork: ForkName,
        keep: int = 1,
        dry_run: bool = False,
    ) -> tuple[list[str], list[str]]:
        """Remove old unmanaged Proton releases.

        Keeps all versions currently referenced by symlinks, plus the N newest
        unlinked versions. Delegates to the prune_operations submodule.

        Args:
            extract_dir: Directory containing Proton installations
            fork: The Proton fork name to prune
            keep: Number of newest unlinked versions to retain (0 = prune all)
            dry_run: If True, only report what would be removed

        Returns:
            Tuple of (kept_versions, pruned_versions) lists

        Raises:
            ValueError: If keep is less than 0
        """
        return _prune_releases(
            extract_dir, fork, keep, dry_run, self.file_system_client
        )
