"""Prune operations for removing old unmanaged Proton releases.

Provides standalone functions for computing prune plans and executing
prune removals, independent of the LinkManager class.
"""

import logging
from pathlib import Path

from .common import (
    FileSystemClientProtocol,
    ForkName,
    VersionCandidateList,
    VersionTuple,
)
from .exceptions import LinkManagementError
from .filesystem import FileSystemClient
from .version_finder import find_version_candidates

logger = logging.getLogger(__name__)


def get_installed_versions(
    extract_dir: Path, fork: ForkName, file_system: FileSystemClientProtocol
) -> list[str]:
    """Get list of currently installed version tags for a fork.

    Finds all version directories for the specified fork and returns
    their tag names, sorted by version (newest first).

    Args:
        extract_dir: Directory to search for installed versions
        fork: The Proton fork name
        file_system: File system client

    Returns:
        List of version tag strings, sorted newest first
    """
    candidates = find_version_candidates(extract_dir, fork, file_system)

    if not candidates:
        return []

    # Remove duplicates, preferring standard naming
    candidates = _deduplicate_candidates(candidates)

    # Sort by version (newest first)
    candidates.sort(key=lambda t: t[0], reverse=True)

    # Extract tag names from directory paths
    return [path.name for _, path in candidates]


def get_linked_versions(
    extract_dir: Path, fork: ForkName, file_system: FileSystemClientProtocol
) -> set[str]:
    """Get set of version directories currently referenced by symlinks.

    Resolves all managed symlinks for the fork and returns the directory
    names they point to.

    Args:
        extract_dir: Directory to search for symlinks
        fork: The Proton fork name
        file_system: File system client

    Returns:
        Set of directory names currently linked
    """
    from .link_status import list_links as _list_links

    linked: set[str] = set()
    links_info = _list_links(extract_dir, fork, file_system)

    for target_path in links_info.values():
        if target_path is not None:
            linked.add(Path(target_path).name)

    return linked


def _deduplicate_candidates(
    candidates: VersionCandidateList,
) -> VersionCandidateList:
    """Remove duplicate versions, preferring standard naming.

    Args:
        candidates: List of (version, path) tuples

    Returns:
        Deduplicated list of (version, path) tuples
    """
    seen: set[VersionTuple] = set()
    deduplicated: VersionCandidateList = []

    for version, path in candidates:
        if version not in seen:
            seen.add(version)
            deduplicated.append((version, path))

    return deduplicated


def compute_prune_plan(
    extract_dir: Path,
    fork: ForkName,
    keep: int,
    file_system: FileSystemClientProtocol,
) -> tuple[list[str], list[str]]:
    """Compute which versions to keep and which to prune.

    Args:
        extract_dir: Directory containing Proton installations
        fork: The Proton fork name to prune
        keep: Number of newest versions to retain
        file_system: File system client

    Returns:
        Tuple of (kept_versions, pruned_versions) lists
    """
    all_versions = get_installed_versions(extract_dir, fork, file_system)
    if not all_versions:
        logger.info(f"No {fork.value} installations found to prune")
        return [], []

    linked_versions = get_linked_versions(extract_dir, fork, file_system)
    kept_versions: list[str] = all_versions[:keep]
    prune_candidates = all_versions[keep:]

    # Never prune linked versions (protects active prefixes)
    pruned_versions = [v for v in prune_candidates if v not in linked_versions]

    # Report any linked versions that would have been pruned
    protected_versions = [v for v in prune_candidates if v in linked_versions]
    if protected_versions:
        logger.debug(
            f"Protected {len(protected_versions)} linked version(s) from pruning: "
            f"{', '.join(protected_versions)}"
        )

    return kept_versions, pruned_versions


def execute_prune_removals(
    extract_dir: Path,
    fork: ForkName,
    pruned_versions: list[str],
    file_system: FileSystemClientProtocol,
) -> None:
    """Execute the actual removal of pruned versions.

    Args:
        extract_dir: Directory containing Proton installations
        fork: The Proton fork name to prune
        pruned_versions: List of version tags to remove
        file_system: File system client
    """
    from .release_operations import remove_release as _remove_release

    logger.info(f"Pruning {len(pruned_versions)} old {fork.value} release(s)...")
    for version in pruned_versions:
        try:
            _remove_release(extract_dir, version, fork, file_system)
            logger.info(f"  Removed: {version}")
        except LinkManagementError as e:
            logger.warning(f"  Failed to remove {version}: {e}")


def prune_releases(
    extract_dir: Path,
    fork: ForkName,
    keep: int = 3,
    dry_run: bool = False,
    file_system: FileSystemClientProtocol | None = None,
) -> tuple[list[str], list[str]]:
    """Remove old unmanaged Proton releases, keeping the N newest versions.

    Identifies installed versions that are not currently referenced by
    symlinks and removes them, keeping only the newest versions
    (default: 3, matching symlink strategy).

    Args:
        extract_dir: Directory containing Proton installations
        fork: The Proton fork name to prune
        keep: Number of newest versions to retain (default: 3)
        dry_run: If True, only report what would be removed
        file_system: File system client (uses default if None)

    Returns:
        Tuple of (kept_versions, pruned_versions) lists

    Raises:
        ValueError: If keep is less than 1
    """
    if keep < 1:
        raise ValueError("keep must be at least 1")

    if file_system is None:
        file_system = FileSystemClient()

    kept, pruned = compute_prune_plan(extract_dir, fork, keep, file_system)

    if not pruned:
        return kept, []

    if dry_run:
        return kept, pruned

    execute_prune_removals(extract_dir, fork, pruned, file_system)
    return kept, pruned
