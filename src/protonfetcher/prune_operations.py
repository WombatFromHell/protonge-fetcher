"""Prune operations for removing old unmanaged Proton releases.

Provides standalone functions for computing prune plans and executing
prune removals, independent of the LinkManager class.
"""

import logging
from pathlib import Path

from .common import (
    FileSystemClientProtocol,
    ForkName,
)
from .dirs import get_link_names
from .exceptions import LinkManagementError
from .filesystem import FileSystemClient
from .link_status import get_installed_versions
from .release_operations import remove_release as _remove_release

logger = logging.getLogger(__name__)


def compute_prune_plan(
    extract_dir: Path,
    fork: ForkName,
    keep: int,
    file_system: FileSystemClientProtocol | None = None,
) -> tuple[list[str], list[str]]:
    """Compute which versions to keep and which to prune.

    Respects symlink hierarchy: keeps the N newest versions referenced by
    the first N managed symlinks (main, fb1, fb2). Extra symlinks beyond N
    and their target directories are pruned.

    Args:
        extract_dir: Directory containing Proton installations
        fork: The Proton fork name to prune
        keep: Number of newest versions to retain (via symlinks)
        file_system: File system client

    Returns:
        Tuple of (kept_versions, pruned_versions) lists
    """
    file_system = file_system or FileSystemClient()
    all_versions = get_installed_versions(extract_dir, fork, file_system)
    if not all_versions:
        logger.info(f"No {fork.value} installations found to prune")
        return [], []

    # Get symlink paths for this fork
    main, fb1, fb2 = get_link_names(extract_dir, fork)
    symlink_paths = [main, fb1, fb2]

    # Build mapping: symlink_path -> target_dir_name
    symlink_targets: dict[Path, str] = {}
    for link in symlink_paths:
        if file_system.is_symlink(link):
            try:
                target = file_system.resolve(link)
                symlink_targets[link] = target.name
            except OSError:
                pass  # broken symlink

    if symlink_targets:
        # Symlink-aware mode: keep targets of first N symlinks, prune extras
        kept: set[str] = set()
        for link in symlink_paths[:keep]:
            if link in symlink_targets:
                kept.add(symlink_targets[link])

        extra_symlink_targets: set[str] = set()
        for link in symlink_paths[keep:]:
            if link in symlink_targets:
                extra_symlink_targets.add(symlink_targets[link])

        pruned: list[str] = []
        # First: versions referenced by extra symlinks (symlink + dir removed together)
        for v in all_versions:
            if v in extra_symlink_targets and v not in kept:
                pruned.append(v)
        # Then: other unlinked versions beyond keep count
        for v in all_versions:
            if v not in kept and v not in pruned:
                pruned.append(v)

        # Return kept in all_versions (newest-first) order for determinism
        return [v for v in all_versions if v in kept], pruned
    else:
        # No symlinks: fall back to version-based keeping
        kept_versions = all_versions[:keep]
        pruned_versions = all_versions[keep:]
        return kept_versions, pruned_versions


def execute_prune_removals(
    extract_dir: Path,
    fork: ForkName,
    pruned_versions: list[str],
    file_system: FileSystemClientProtocol | None = None,
) -> None:
    """Execute the actual removal of pruned versions.

    Args:
        extract_dir: Directory containing Proton installations
        fork: The Proton fork name to prune
        pruned_versions: List of version tags to remove
        file_system: File system client
    """
    file_system = file_system or FileSystemClient()
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
    """Remove old Proton releases beyond the keep count.

    Respects symlink hierarchy: keeps the first N managed symlinks (main,
    fb1, fb2) pointing to the N newest versions. Extra symlinks beyond N
    and their target directories are pruned.

    When keep=0, all versions are pruned (no versions kept).

    Args:
        extract_dir: Directory containing Proton installations
        fork: The Proton fork name to prune
        keep: Number of symlinked versions to retain (0 = prune all)
        dry_run: If True, only report what would be removed
        file_system: File system client

    Returns:
        Tuple of (kept_versions, pruned_versions) lists

    Raises:
        ValueError: If keep is less than 0
    """
    if keep < 0:
        raise ValueError("keep must be at least 0")

    if file_system is None:
        file_system = FileSystemClient()

    kept, pruned = compute_prune_plan(extract_dir, fork, keep, file_system)

    if not pruned:
        return kept, []

    if dry_run:
        return kept, pruned

    execute_prune_removals(extract_dir, fork, pruned, file_system)
    return kept, pruned
