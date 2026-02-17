"""Link manager implementation for ProtonFetcher."""

import logging
import re
from pathlib import Path
from typing import Dict, Optional

from .common import (
    DEFAULT_TIMEOUT,
    FileSystemClientProtocol,
    ForkName,
    LinkSpecList,
    SymlinkMapping,
    SymlinkSpec,
    VersionCandidateList,
    VersionGroups,
    VersionTuple,
)
from .exceptions import LinkManagementError
from .utils import parse_version

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
        match fork:
            case ForkName.PROTON_EM:
                return (
                    extract_dir / "Proton-EM",
                    extract_dir / "Proton-EM-Fallback",
                    extract_dir / "Proton-EM-Fallback2",
                )
            case ForkName.CACHYOS:
                return (
                    extract_dir / "CachyOS",
                    extract_dir / "CachyOS-Fallback",
                    extract_dir / "CachyOS-Fallback2",
                )
            case ForkName.GE_PROTON:
                return (
                    extract_dir / "GE-Proton",
                    extract_dir / "GE-Proton-Fallback",
                    extract_dir / "GE-Proton-Fallback2",
                )
            case _:  # Handle any unhandled cases
                # This shouldn't happen with ForkName, but added for exhaustiveness
                return (
                    extract_dir / "",
                    extract_dir / "",
                    extract_dir / "",
                )

    def _find_ge_proton_tag_directory(self, extract_dir: Path, tag: str) -> Path:
        """Find tag directory for GE-Proton.

        Args:
            extract_dir: Directory to search
            tag: Release tag

        Returns:
            Path to the found directory

        Raises:
            LinkManagementError: If directory not found
        """
        tag_dir_path = extract_dir / tag
        if self.file_system_client.exists(
            tag_dir_path
        ) and self.file_system_client.is_dir(tag_dir_path):
            return tag_dir_path

        raise LinkManagementError(f"Manual release directory not found: {tag_dir_path}")

    def _find_proton_em_tag_directory(self, extract_dir: Path, tag: str) -> Path:
        """Find tag directory for Proton-EM.

        Args:
            extract_dir: Directory to search
            tag: Release tag

        Returns:
            Path to the found directory

        Raises:
            LinkManagementError: If directory not found
        """
        proton_em_dir = extract_dir / f"proton-{tag}"
        if self.file_system_client.exists(
            proton_em_dir
        ) and self.file_system_client.is_dir(proton_em_dir):
            return proton_em_dir

        # If not found, also try without proton- prefix
        tag_dir_path = extract_dir / tag
        if self.file_system_client.exists(
            tag_dir_path
        ) and self.file_system_client.is_dir(tag_dir_path):
            return tag_dir_path

        raise LinkManagementError(
            f"Manual release directory not found: {extract_dir / tag} or {proton_em_dir}"
        )

    def _find_cachyos_tag_directory(self, extract_dir: Path, tag: str) -> Path:
        """Find tag directory for CachyOS.

        Args:
            extract_dir: Directory to search
            tag: Release tag

        Returns:
            Path to the found directory

        Raises:
            LinkManagementError: If directory not found
        """
        # CachyOS archives extract to directory with -x86_64 suffix
        # e.g., tag 'cachyos-10.0-20260207-slr' extracts to 'proton-cachyos-10.0-20260207-slr-x86_64'
        cachyos_dir = extract_dir / f"proton-{tag}-x86_64"
        if self.file_system_client.exists(
            cachyos_dir
        ) and self.file_system_client.is_dir(cachyos_dir):
            return cachyos_dir

        # If not found, also try without -x86_64 suffix
        cachyos_dir_no_suffix = extract_dir / f"proton-{tag}"
        if self.file_system_client.exists(
            cachyos_dir_no_suffix
        ) and self.file_system_client.is_dir(cachyos_dir_no_suffix):
            return cachyos_dir_no_suffix

        # If not found, also try without proton- prefix
        tag_dir_path = extract_dir / tag
        if self.file_system_client.exists(
            tag_dir_path
        ) and self.file_system_client.is_dir(tag_dir_path):
            return tag_dir_path

        raise LinkManagementError(
            f"Manual release directory not found: {extract_dir / tag}, {cachyos_dir}, or {cachyos_dir_no_suffix}"
        )

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
        if fork == ForkName.PROTON_EM:
            return self._find_proton_em_tag_directory(extract_dir, tag)
        elif fork == ForkName.CACHYOS:
            return self._find_cachyos_tag_directory(extract_dir, tag)
        elif fork == ForkName.GE_PROTON:
            return self._find_ge_proton_tag_directory(extract_dir, tag)
        else:
            raise ValueError(f"Unsupported fork: {fork}")

    def _get_tag_name(self, entry: Path, fork: ForkName) -> str:
        """Get the tag name from the directory entry, handling Proton-EM prefix."""
        if fork == ForkName.PROTON_EM and entry.name.startswith("proton-"):
            return entry.name[7:]  # Remove "proton-" prefix
        elif fork == ForkName.CACHYOS and entry.name.startswith("proton-"):
            # Remove "proton-" prefix and "-x86_64" suffix if present
            name = entry.name[7:]  # Remove "proton-" prefix
            if name.endswith("-x86_64"):
                name = name[:-7]  # Remove "-x86_64" suffix
            return name
        else:
            return entry.name

    def _should_skip_directory(self, tag_name: str, fork: ForkName) -> bool:
        """Check if directory should be skipped based on fork."""
        if fork == ForkName.PROTON_EM and tag_name.startswith("GE-Proton"):
            # Skip GE-Proton directories when processing Proton-EM
            return True
        elif fork == ForkName.CACHYOS and tag_name.startswith("GE-Proton"):
            # Skip GE-Proton directories when processing CachyOS
            return True
        elif fork == ForkName.GE_PROTON and (
            tag_name.startswith("EM-")
            or (tag_name.startswith("proton-") and "EM-" in tag_name)
        ):
            # Skip Proton-EM directories when processing GE-Proton
            return True
        elif fork == ForkName.GE_PROTON and (
            tag_name.startswith("cachyos-")
            or (tag_name.startswith("proton-") and "cachyos" in tag_name.lower())
        ):
            # Skip CachyOS directories when processing GE-Proton
            return True
        elif fork == ForkName.PROTON_EM and (
            tag_name.startswith("cachyos-")
            or (tag_name.startswith("proton-") and "cachyos" in tag_name.lower())
        ):
            # Skip CachyOS directories when processing Proton-EM
            return True
        return False

    def _is_valid_proton_directory(self, entry: Path, fork: ForkName) -> bool:
        """Validate that the directory name matches expected pattern for the fork."""
        match fork:
            case ForkName.GE_PROTON:
                # GE-Proton directories should match pattern: GE-Proton{major}-{minor}
                ge_pattern = r"^GE-Proton\d+-\d+$"
                return bool(re.match(ge_pattern, entry.name))
            case ForkName.PROTON_EM:
                # Proton-EM directories should match pattern: proton-EM-{major}.{minor}-{patch}
                # or EM-{major}.{minor}-{patch}
                em_pattern1 = r"^proton-EM-\d+\.\d+-\d+$"
                em_pattern2 = r"^EM-\d+\.\d+-\d+$"
                return bool(
                    re.match(em_pattern1, entry.name)
                    or re.match(em_pattern2, entry.name)
                )
            case ForkName.CACHYOS:
                # CachyOS directories should match pattern: proton-cachyos-{major}.{minor}-{date}-slr-x86_64
                # or cachyos-{major}.{minor}-{date}-slr (with or without -x86_64 suffix)
                cachyos_pattern1 = r"^proton-cachyos-\d+\.\d+-\d+-slr(-x86_64)?$"
                cachyos_pattern2 = r"^cachyos-\d+\.\d+-\d+-slr$"
                return bool(
                    re.match(cachyos_pattern1, entry.name)
                    or re.match(cachyos_pattern2, entry.name)
                )

    def find_version_candidates(
        self, extract_dir: Path, fork: ForkName
    ) -> VersionCandidateList:
        """Find all directories that look like Proton builds and parse their versions."""
        candidates: list[tuple[VersionTuple, Path]] = []
        for entry in self.file_system_client.iterdir(extract_dir):
            if self.file_system_client.is_dir(
                entry
            ) and not self.file_system_client.is_symlink(entry):
                tag_name = self._get_tag_name(entry, fork)

                # Skip directories that clearly belong to the other fork
                if self._should_skip_directory(tag_name, fork):
                    continue

                # For each fork, validate that the directory name matches expected pattern
                # This prevents non-Proton directories like "LegacyRuntime" from being included
                if self._is_valid_proton_directory(entry, fork):
                    # use the directory name as tag for comparison
                    candidates.append((parse_version(tag_name, fork), entry))
        return candidates

    def _create_symlink_specs(
        self, main: Path, fb1: Path, fb2: Path, top_3: VersionCandidateList
    ) -> LinkSpecList:
        """Create SymlinkSpec objects for the top 3 versions."""
        specs: LinkSpecList = []

        if len(top_3) > 0:
            specs.append(
                SymlinkSpec(link_path=main, target_path=top_3[0][1], priority=0)
            )

        if len(top_3) > 1:
            specs.append(
                SymlinkSpec(link_path=fb1, target_path=top_3[1][1], priority=1)
            )

        if len(top_3) > 2:
            specs.append(
                SymlinkSpec(link_path=fb2, target_path=top_3[2][1], priority=2)
            )

        return specs

    def _cleanup_unwanted_links(
        self, main: Path, fb1: Path, fb2: Path, wants: SymlinkMapping
    ) -> None:
        """Remove unwanted symlinks and any real directories that conflict with wanted symlinks."""
        for link in (main, fb1, fb2):
            if self.file_system_client.is_symlink(link) and link not in wants:
                self.file_system_client.unlink(link)
            # If link exists but is a real directory, remove it (regardless of whether it's wanted)
            # This handles the case where a real directory has the same name as a symlink that needs to be created
            elif self.file_system_client.exists(
                link
            ) and not self.file_system_client.is_symlink(link):
                self.file_system_client.rmtree(link)

    def _compare_targets(self, current_target: Path, expected_target: Path) -> bool:
        """Compare if two targets are the same by checking the resolved paths."""
        try:
            resolved_current_target = self.file_system_client.resolve(current_target)
            resolved_expected_target = self.file_system_client.resolve(expected_target)
            return resolved_current_target == resolved_expected_target
        except OSError:
            # The target directory doesn't exist yet (common case)
            # We can't directly compare resolved paths, so return False to update the symlink
            return False

    def _handle_existing_symlink(self, link: Path, expected_target: Path) -> None:
        """Handle an existing symlink to check if it points to the correct target."""
        try:
            current_target = self.file_system_client.resolve(link)
            # The target is a directory path that may or may not exist yet
            # If it doesn't exist, we can't resolve it, so we need special handling
            paths_match = self._compare_targets(current_target, expected_target)
            if paths_match:
                return  # already correct
            else:
                # Paths don't match, remove symlink to update to new target
                self.file_system_client.unlink(link)
        except OSError:
            # If resolve fails on the current symlink (broken symlink), remove it
            self.file_system_client.unlink(link)

    def _cleanup_existing_path_before_symlink(
        self, link: Path, expected_target: Path
    ) -> None:
        """Clean up existing path before creating a symlink."""
        # Double check: If link exists as a real directory, remove it before creating symlink
        if self.file_system_client.exists(
            link
        ) and not self.file_system_client.is_symlink(link):
            self.file_system_client.rmtree(link)
        # If link is a symlink, check if it points to the correct target
        elif self.file_system_client.is_symlink(link):
            self._handle_existing_symlink(link, expected_target)

        # Final check: make sure there's nothing at link path before creating symlink
        if self.file_system_client.exists(link):
            # This should not happen with correct logic above, but for safety
            if self.file_system_client.is_symlink(link):
                self.file_system_client.unlink(link)
            else:
                self.file_system_client.rmtree(link)

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
        return self._create_symlinks_internal(main, fb1, fb2, top_3)

    def create_symlinks_for_test(
        self, extract_dir: Path, target_path: Path, fork: ForkName
    ) -> bool:
        """Create symlinks for test usage.

        Args:
            extract_dir: Directory where symlinks will be created
            target_path: Target directory to link to
            fork: The Proton fork name

        Returns:
            True if symlink creation was attempted

        Raises:
            LinkManagementError: If target directory doesn't exist
        """
        return self._create_symlinks_from_test(extract_dir, target_path, fork)

    def _create_symlinks_internal(
        self,
        main: Path,
        fb1: Path,
        fb2: Path,
        top_3: VersionCandidateList,
    ) -> bool:
        """Internal implementation for creating symlinks with 4 parameters."""
        # Create SymlinkSpec objects for all symlinks we want to create
        wanted_specs = self._create_symlink_specs(main, fb1, fb2, top_3)

        # Build a mapping from link path to target path
        wants: Dict[Path, Path] = {
            spec.link_path: spec.target_path for spec in wanted_specs
        }

        # First pass: Remove unwanted symlinks and any real directories that conflict with wanted symlinks
        self._cleanup_unwanted_links(main, fb1, fb2, wants)

        for link, target in wants.items():
            self._cleanup_existing_path_before_symlink(link, target)
            # Calculate relative path from the link location to the target for relative symlinks
            # If target is not in a subdirectory of link's parent, use absolute path
            try:
                relative_target = target.relative_to(link.parent)
            except ValueError:
                # If target is not a subpath of link.parent, use absolute path
                relative_target = target
            # Use target_is_directory=True to correctly handle directory symlinks
            try:
                self.file_system_client.symlink_to(
                    link, relative_target, target_is_directory=True
                )
                logger.info("Created symlink %s -> %s", link.name, relative_target)
            except OSError as e:
                logger.error(
                    "Failed to create symlink %s -> %s: %s", link.name, target.name, e
                )
                # Don't re-raise to handle gracefully as expected by test
                # The function should complete without crashing even if symlink creation fails
                continue  # Continue to the next link instead of failing the entire function

        return True

    def _create_symlinks_from_test(
        self,
        extract_dir: Path,
        target_path: Path,
        fork: ForkName,
    ) -> bool:
        """Implementation for test usage: creating all 3 symlinks to the same target."""
        # Check if target directory exists - if not, raise LinkManagementError as expected by tests
        if not self.file_system_client.exists(
            target_path
        ) or not self.file_system_client.is_dir(target_path):
            raise LinkManagementError(f"Target directory does not exist: {target_path}")

        main, fb1, fb2 = self.get_link_names_for_fork(extract_dir, fork)

        # Create all 3 symlinks to the same target_path
        wanted_specs = [
            SymlinkSpec(link_path=main, target_path=target_path, priority=0),
            SymlinkSpec(link_path=fb1, target_path=target_path, priority=1),
            SymlinkSpec(link_path=fb2, target_path=target_path, priority=2),
        ]

        # Build a mapping from link path to target path
        wants: Dict[Path, Path] = {
            spec.link_path: spec.target_path for spec in wanted_specs
        }

        # First pass: Remove unwanted symlinks and any real directories that conflict with wanted symlinks
        self._cleanup_unwanted_links(main, fb1, fb2, wants)

        for link, target in wants.items():
            self._cleanup_existing_path_before_symlink(link, target)
            # Calculate relative path from the link location to the target for relative symlinks
            # If target is not in a subdirectory of link's parent, use absolute path
            try:
                relative_target = target.relative_to(link.parent)
            except ValueError:
                # If target is not a subpath of link.parent, use absolute path
                relative_target = target
            # Use target_is_directory=True to correctly handle directory symlinks
            try:
                self.file_system_client.symlink_to(
                    link, relative_target, target_is_directory=True
                )
                logger.info("Created symlink %s -> %s", link.name, relative_target)
            except OSError as e:
                logger.error(
                    "Failed to create symlink %s -> %s: %s", link.name, target.name, e
                )
                # Don't re-raise to handle gracefully as expected by test
                # The function should complete without crashing even if symlink creation fails
                continue  # Continue to the next link instead of failing the entire function

        return True

    def list_links(
        self, extract_dir: Path, fork: ForkName = ForkName.GE_PROTON
    ) -> dict[str, str | None]:
        """
        List recognized symbolic links and their associated Proton fork folders.

        Args:
            extract_dir: Directory to search for links
            fork: The Proton fork name to determine link naming

        Returns:
            Dictionary mapping link names to their target paths (or None if link doesn't exist)
        """
        # Get symlink names for the fork
        main, fb1, fb2 = self.get_link_names_for_fork(extract_dir, fork)

        links_info: dict[str, str | None] = {}

        # Check each link and get its target
        for link_name in [main, fb1, fb2]:
            if self.file_system_client.exists(
                link_name
            ) and self.file_system_client.is_symlink(link_name):
                try:
                    target_path = self.file_system_client.resolve(link_name)
                    links_info[link_name.name] = str(target_path)
                except OSError:
                    # Broken symlink, return None
                    links_info[link_name.name] = None
            else:
                links_info[link_name.name] = None

        return links_info

    def _determine_release_path(
        self, extract_dir: Path, tag: str, fork: ForkName
    ) -> Path:
        """Determine the correct release path, considering Proton-EM format."""
        release_path = extract_dir / tag

        # Also handle Proton-EM and CachyOS format with "proton-" prefix
        if fork in (ForkName.PROTON_EM, ForkName.CACHYOS):
            proton_prefixed_path = extract_dir / f"proton-{tag}"
            if not self.file_system_client.exists(
                release_path
            ) and self.file_system_client.exists(proton_prefixed_path):
                release_path = proton_prefixed_path

            # For CachyOS, also check with -x86_64 suffix
            if fork == ForkName.CACHYOS:
                cachyos_path = extract_dir / f"proton-{tag}-x86_64"
                if not self.file_system_client.exists(
                    release_path
                ) and self.file_system_client.exists(cachyos_path):
                    release_path = cachyos_path

        return release_path

    def _check_release_exists(self, release_path: Path) -> None:
        """Check if the release directory exists, raise error if not."""
        if not self.file_system_client.exists(release_path):
            raise LinkManagementError(
                f"Release directory does not exist: {release_path}"
            )

    def _identify_links_to_remove(
        self, extract_dir: Path, release_path: Path, fork: ForkName
    ) -> list[Path]:
        """Identify symbolic links that point to the release directory."""
        # Get symlink names for the fork to check if they point to this release
        main, fb1, fb2 = self.get_link_names_for_fork(extract_dir, fork)

        # Identify links that point to this release directory
        links_to_remove: list[Path] = []
        for link in [main, fb1, fb2]:
            if self.file_system_client.exists(
                link
            ) and self.file_system_client.is_symlink(link):
                try:
                    target_path = self.file_system_client.resolve(link)
                    if target_path == release_path:
                        links_to_remove.append(link)
                except OSError:
                    # Broken symlink - remove it if it points to the release directory
                    links_to_remove.append(link)

        return links_to_remove

    def _remove_release_directory(self, release_path: Path) -> None:
        """Remove the release directory."""
        try:
            self.file_system_client.rmtree(release_path)
            logger.info(f"Removed release directory: {release_path}")
        except Exception as e:
            raise LinkManagementError(
                f"Failed to remove release directory {release_path}: {e}"
            )

    def _remove_symbolic_links(self, links_to_remove: list[Path]) -> None:
        """Remove the associated symbolic links."""
        for link in links_to_remove:
            try:
                self.file_system_client.unlink(link)
                logger.info(f"Removed symbolic link: {link}")
            except Exception as e:
                logger.error(f"Failed to remove symbolic link {link}: {e}")

    def remove_release(
        self, extract_dir: Path, tag: str, fork: ForkName = ForkName.GE_PROTON
    ) -> bool:
        """
        Remove a specific Proton fork release folder and its associated symbolic links.

        Args:
            extract_dir: Directory containing the release folder
            tag: The release tag to remove
            fork: The Proton fork name to determine link naming

        Returns:
            True if the removal was successful, False otherwise
        """
        release_path = self._determine_release_path(extract_dir, tag, fork)

        # Check if the release directory exists
        self._check_release_exists(release_path)

        # Identify links that point to this release directory
        links_to_remove = self._identify_links_to_remove(
            extract_dir, release_path, fork
        )

        # Remove the release directory
        self._remove_release_directory(release_path)

        # Remove the associated symbolic links that point to this release
        self._remove_symbolic_links(links_to_remove)

        # Regenerate the link management system to ensure consistency
        self.manage_proton_links(extract_dir, tag, fork)

        return True

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
            # CachyOS uses "proton-" prefix and "-x86_64" suffix
            return extract_dir / f"proton-{tag}-x86_64"
        else:
            # Proton-EM uses "proton-" prefix
            return extract_dir / f"proton-{tag}"

    def _log_manual_release_warning(self, expected_path: Path) -> None:
        """Log a warning when expected manual release directory is not found.

        Args:
            expected_path: The expected directory path that was not found
        """
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

    def _deduplicate_candidates(
        self, candidates: VersionCandidateList
    ) -> VersionCandidateList:
        """Remove duplicate versions, preferring directories with standard naming over prefixed naming."""
        # Group candidates by parsed version
        version_groups: VersionGroups = {}
        for parsed_version, directory_path in candidates:
            if parsed_version not in version_groups:
                version_groups[parsed_version] = []
            version_groups[parsed_version].append(directory_path)

        # For each group of directories with the same version, prefer the canonical name
        unique_candidates: VersionCandidateList = []
        for parsed_version, directories in version_groups.items():
            # Prefer directories without "proton-" prefix for Proton-EM, or standard names in general
            # Sort by directory name to have a consistent preference - shorter/simpler names first
            preferred_dir = min(
                directories,
                key=lambda d: (
                    # Prefer directories without 'proton-' prefix
                    1 if d.name.startswith("proton-") else 0,
                    # Then by name length (shorter names preferred)
                    len(d.name),
                    # Then by name itself for consistent ordering
                    d.name,
                ),
            )
            unique_candidates.append((parsed_version, preferred_dir))

        return unique_candidates

    def _handle_manual_release_candidates(
        self,
        tag: str,
        fork: ForkName,
        candidates: VersionCandidateList,
        tag_dir: Optional[Path],
    ) -> VersionCandidateList:
        """Handle candidates for manual releases."""
        # For manual releases, add the manual tag to candidates and sort
        tag_version = parse_version(tag, fork)

        # Check if this version is already in candidates to avoid duplicates
        existing_versions: set[VersionTuple] = {
            candidate[0] for candidate in candidates
        }
        if tag_version not in existing_versions and tag_dir is not None:
            candidates.append((tag_version, tag_dir))

        # Sort all candidates including the manual tag
        candidates.sort(key=lambda t: t[0], reverse=True)

        # Take top 3
        top_3: list[tuple[VersionTuple, Path]] = candidates[:3]
        return top_3

    def _handle_regular_release_candidates(
        self, candidates: VersionCandidateList
    ) -> VersionCandidateList:
        """Handle candidates for regular releases."""
        # sort descending by version (newest first)
        candidates.sort(key=lambda t: t[0], reverse=True)
        top_3: VersionCandidateList = candidates[:3]
        return top_3

    def _get_top_3_candidates(
        self,
        extract_dir: Path,
        tag: str,
        fork: ForkName,
        is_manual_release: bool,
        tag_dir: Optional[Path],
    ) -> Optional[VersionCandidateList]:
        """Get the top 3 version candidates for symlinks.

        Returns:
            List of top 3 (version, path) tuples, or None if no candidates found
        """
        candidates = self.find_version_candidates(extract_dir, fork)
        if not candidates:
            return None

        candidates = self._deduplicate_candidates(candidates)

        if is_manual_release and tag_dir is not None:
            top_3 = self._handle_manual_release_candidates(
                tag, fork, candidates, tag_dir
            )
        else:
            top_3 = self._handle_regular_release_candidates(candidates)

        if not top_3:
            return None

        return top_3

    def _build_expected_link_mapping(
        self,
        link_names: tuple[Path, Path, Path],
        top_3: VersionCandidateList,
    ) -> dict[str, str]:
        """Build expected link mapping from link names and top 3 candidates.

        Returns:
            Dict mapping link name to expected target path
        """
        expected_links: dict[str, str] = {}
        for link_name, (version, target_path) in zip(link_names, top_3):
            expected_links[link_name.name] = str(target_path)
        return expected_links

    def _compare_link_targets(
        self,
        current_links: dict[str, str | None],
        expected_links: dict[str, str],
    ) -> bool:
        """Compare current vs expected link targets.

        Returns:
            True if all links match expected targets, False otherwise
        """
        for link_name, expected_target in expected_links.items():
            current_target = current_links.get(link_name)

            if current_target is None:
                return False

            try:
                expected_path = Path(expected_target).resolve()
                current_path = Path(current_target).resolve()
                if expected_path != current_path:
                    return False
            except OSError:
                return False

        return True

    def are_links_up_to_date(
        self,
        extract_dir: Path,
        tag: str,
        fork: ForkName = ForkName.GE_PROTON,
        is_manual_release: bool = False,
    ) -> bool:
        """
        Check if existing symlinks are already correct and up-to-date.

        This method determines what the symlinks should point to and compares
        it with the current state, returning True if no changes are needed.

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

        # For manual releases, check if target directory exists
        tag_dir = self._handle_manual_release_directory(
            extract_dir, tag, fork, is_manual_release
        )

        if is_manual_release and tag_dir is None:
            return False

        # Get top 3 candidates
        top_3 = self._get_top_3_candidates(
            extract_dir, tag, fork, is_manual_release, tag_dir
        )
        if top_3 is None:
            return False

        # Get current link status
        current_links = self.list_links(extract_dir, fork)

        # Build expected mapping
        expected_links = self._build_expected_link_mapping(link_names, top_3)

        # Compare current vs expected
        return self._compare_link_targets(current_links, expected_links)

    def manage_proton_links(
        self,
        extract_dir: Path,
        tag: str,
        fork: ForkName = ForkName.GE_PROTON,
        is_manual_release: bool = False,
    ) -> bool:
        """
        Ensure the three symlinks always point to the three *newest* extracted
        versions, regardless of the order in which they were downloaded.

        Returns:
            True if the operation was successful
        """
        main, fb1, fb2 = self._get_link_names(extract_dir, fork)

        # For manual releases, first check if the target directory exists
        tag_dir = self._handle_manual_release_directory(
            extract_dir, tag, fork, is_manual_release
        )

        # If it was manual release and no directory found, return early
        if is_manual_release and tag_dir is None:
            return True

        # Find all version candidates
        candidates = self.find_version_candidates(extract_dir, fork)

        if not candidates:  # nothing to do
            logger.warning("No extracted Proton directories found – not touching links")
            return True

        # Remove duplicate versions, preferring standard naming
        candidates = self._deduplicate_candidates(candidates)

        # Handle different logic for manual vs regular releases
        if is_manual_release and tag_dir is not None:
            top_3 = self._handle_manual_release_candidates(
                tag, fork, candidates, tag_dir
            )
        else:
            top_3 = self._handle_regular_release_candidates(candidates)

        # Create the symlinks
        self.create_symlinks(main, fb1, fb2, top_3)
        return True
