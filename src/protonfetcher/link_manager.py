"""Link manager implementation for ProtonFetcher."""

import logging
from pathlib import Path
from typing import Optional

from .candidate_selection import select_top_3_candidates as _select_top_3
from .common import (
    DEFAULT_TIMEOUT,
    FORKS,
    FileSystemClientProtocol,
    ForkName,
    VersionCandidateList,
)
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
    list_links as _list_links,
)
from .prune_operations import prune_releases as _prune_releases
from .release_operations import remove_release as _remove_release
from .symlink_operations import create_symlinks as _create_symlinks
from .version_finder import (
    _deduplicate_candidates,
    find_version_candidates,
)

logger = logging.getLogger(__name__)


def resolve_directory(
    extract_dir: Path,
    tag: str,
    fork: ForkName,
    file_system: FileSystemClientProtocol,
) -> Path:
    """Resolve the extracted directory for a release tag using fork-specific templates.

    Tries each directory name template from ForkConfig in priority order.

    Args:
        extract_dir: Base directory to search
        tag: Release tag
        fork: The fork name
        file_system: File system client for existence checks

    Returns:
        Path to the found directory

    Raises:
        LinkManagementError: If no template matches an existing directory
    """
    cfg = FORKS[fork]
    for template in cfg.dir_name_templates:
        candidate = extract_dir / template.format(tag=tag)
        if file_system.exists(candidate) and file_system.is_dir(candidate):
            return candidate

    tried = ", ".join(t.format(tag=tag) for t in cfg.dir_name_templates)
    raise LinkManagementError(f"Manual release directory not found: {tried}")


def resolve_directory_candidates(
    extract_dir: Path,
    tag: str,
    fork: ForkName,
) -> list[Path]:
    """Return all candidate directory paths for a tag, in priority order.

    Does not check existence — just generates paths from templates.

    Args:
        extract_dir: Base directory to search
        tag: Release tag
        fork: The fork name

    Returns:
        List of candidate Path objects in priority order
    """
    cfg = FORKS[fork]
    return [extract_dir / t.format(tag=tag) for t in cfg.dir_name_templates]


class LinkManager:
    """Manages symbolic links for Proton installations."""

    def __init__(
        self,
        file_system_client: FileSystemClientProtocol,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.file_system_client = file_system_client
        self.timeout = timeout

    def get_link_names_for_fork(
        self,
        extract_dir: Path,
        fork: ForkName,
    ) -> tuple[Path, Path, Path]:
        """Get the symlink names for a specific fork with extract_dir.

        Args:
            extract_dir: The directory where symlinks will be created
            fork: The Proton fork name

        Returns:
            Tuple of three Path objects: (main, fallback1, fallback2)
        """
        suffixes = FORKS[fork].link_names
        return (
            extract_dir / suffixes[0],
            extract_dir / suffixes[1],
            extract_dir / suffixes[2],
        )

    def _find_tag_directory(self, extract_dir: Path, tag: str, fork: ForkName) -> Path:
        """Find tag directory using fork-specific templates.

        Args:
            extract_dir: Directory to search
            tag: Release tag
            fork: The fork name

        Returns:
            Path to the found directory

        Raises:
            LinkManagementError: If directory not found
        """
        return resolve_directory(extract_dir, tag, fork, self.file_system_client)

    def _validate_find_tag_inputs(
        self,
        extract_dir: Path,
        tag: str,
        fork: ForkName,
    ) -> None:
        """Validate inputs for find_tag_directory.

        Raises:
            ValueError: If inputs are invalid
        """
        if not isinstance(extract_dir, Path):
            raise ValueError(f"extract_dir must be a Path, got {type(extract_dir)}")
        if not isinstance(tag, str) or not tag:
            raise ValueError(f"tag must be a non-empty string, got {tag}")
        if not isinstance(fork, ForkName):
            raise ValueError(f"fork must be a ForkName, got {type(fork)}")

    def find_tag_directory(
        self,
        extract_dir: Path,
        tag: str,
        fork: ForkName,
        is_manual_release: bool = True,
    ) -> Optional[Path]:
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
        # Validate input
        self._validate_find_tag_inputs(extract_dir, tag, fork)

        # Not a manual release
        if not is_manual_release:
            return None

        # Dispatch to fork-specific implementation
        if fork not in FORKS:
            raise ValueError(f"Unsupported fork: {fork}")
        return self._find_tag_directory(extract_dir, tag, fork)

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

    def _deduplicate_candidates(
        self, candidates: VersionCandidateList
    ) -> VersionCandidateList:
        """Remove duplicate versions, preferring standard naming.

        Delegates to the version_finder submodule.
        """
        return _deduplicate_candidates(candidates)

    def _get_link_names(
        self, extract_dir: Path, fork: ForkName
    ) -> tuple[Path, Path, Path]:
        """Get the symlink names for the fork."""
        return self.get_link_names_for_fork(extract_dir, fork)

    def _get_expected_manual_release_path(
        self, extract_dir: Path, tag: str, fork: ForkName
    ) -> Path:
        """Get the expected path for a manual release directory.

        Args:
            extract_dir: Base extraction directory
            tag: Release tag
            fork: Proton fork name

        Returns:
            Expected path for the manual release directory
        """
        if fork == ForkName.GE_PROTON:
            return extract_dir / tag
        elif fork == ForkName.CACHYOS:
            return extract_dir / f"proton-{tag}-x86_64"
        else:
            return extract_dir / f"proton-{tag}"

    def _log_manual_release_warning(self, expected_path: Path) -> None:
        """Log a warning when expected manual release directory is not found."""
        logger.warning("Expected extracted directory does not exist: %s", expected_path)

    def _handle_manual_release_directory(
        self, extract_dir: Path, tag: str, fork: ForkName, is_manual_release: bool
    ) -> Optional[Path]:
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

    def _build_expected_link_mapping(
        self,
        link_names: tuple[Path, Path, Path],
        top_3: VersionCandidateList,
    ) -> dict[str, str]:
        """Build expected link mapping from link names and top 3 candidates.

        Delegates to the link_status submodule.
        """
        return _build_expected_link_mapping(link_names, top_3)

    def _compare_link_targets(
        self,
        current_links: dict[str, str | None],
        expected_links: dict[str, str],
    ) -> bool:
        """Compare current vs expected link targets.

        Delegates to the link_status submodule.
        """
        return _compare_link_targets(current_links, expected_links)

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
        main, fb1, fb2 = self._get_link_names(extract_dir, fork)
        link_names = (main, fb1, fb2)

        tag_dir = self._handle_manual_release_directory(
            extract_dir, tag, fork, is_manual_release
        )

        if is_manual_release and tag_dir is None:
            return False

        top_3 = _select_top_3(
            extract_dir, fork, is_manual_release, tag_dir, self.file_system_client
        )
        if top_3 is None:
            return False

        current_links = self.list_links(extract_dir, fork)
        expected_links = self._build_expected_link_mapping(link_names, top_3)

        return self._compare_link_targets(current_links, expected_links)

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
        main, fb1, fb2 = self._get_link_names(extract_dir, fork)

        tag_dir = self._handle_manual_release_directory(
            extract_dir, tag, fork, is_manual_release
        )

        if is_manual_release and tag_dir is None:
            return True

        top_3 = _select_top_3(
            extract_dir, fork, is_manual_release, tag_dir, self.file_system_client
        )
        if top_3 is None:
            logger.warning("No extracted Proton directories found – not touching links")
            return True

        self.create_symlinks(main, fb1, fb2, top_3)
        return True

    def get_installed_versions(self, extract_dir: Path, fork: ForkName) -> list[str]:
        """Get list of currently installed version tags for a fork.

        Delegates to the prune_operations submodule.

        Args:
            extract_dir: Directory to search for installed versions
            fork: The Proton fork name

        Returns:
            List of version tag strings, sorted newest first
        """
        from .prune_operations import get_installed_versions as _get_installed

        return _get_installed(extract_dir, fork, self.file_system_client)

    def get_linked_versions(self, extract_dir: Path, fork: ForkName) -> set[str]:
        """Get set of version directories currently referenced by symlinks.

        Delegates to the prune_operations submodule.

        Args:
            extract_dir: Directory to search for symlinks
            fork: The Proton fork name

        Returns:
            Set of directory names currently linked
        """
        from .prune_operations import get_linked_versions as _get_linked

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
        """Remove old Proton releases, keeping the N newest versions total.

        Symlinks are part of the keep candidates — they are not protected
        from pruning. Delegates to the prune_operations submodule.

        Args:
            extract_dir: Directory containing Proton installations
            fork: The Proton fork name to prune
            keep: Number of newest versions to retain (default: 1)
            dry_run: If True, only report what would be removed

        Returns:
            Tuple of (kept_versions, pruned_versions) lists

        Raises:
            ValueError: If keep is less than 1
        """
        return _prune_releases(
            extract_dir, fork, keep, dry_run, self.file_system_client
        )
