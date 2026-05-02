"""Symlink operations for Proton installations.

Provides self-contained filesystem operations for creating, cleaning up,
and managing symbolic links that point to Proton version directories.
"""

import logging
from pathlib import Path
from typing import Dict

from .common import (
    FileSystemClientProtocol,
    LinkSpecList,
    SymlinkSpec,
    VersionCandidateList,
)

logger = logging.getLogger(__name__)


def create_symlink_specs(
    main: Path, fb1: Path, fb2: Path, top_3: VersionCandidateList
) -> LinkSpecList:
    """Create SymlinkSpec objects for the top 3 versions.

    Args:
        main: Main symlink path
        fb1: First fallback symlink path
        fb2: Second fallback symlink path
        top_3: List of top 3 (version, path) tuples

    Returns:
        List of SymlinkSpec objects in priority order
    """
    specs: LinkSpecList = []

    if len(top_3) > 0:
        specs.append(SymlinkSpec(link_path=main, target_path=top_3[0][1], priority=0))

    if len(top_3) > 1:
        specs.append(SymlinkSpec(link_path=fb1, target_path=top_3[1][1], priority=1))

    if len(top_3) > 2:
        specs.append(SymlinkSpec(link_path=fb2, target_path=top_3[2][1], priority=2))

    return specs


def cleanup_unwanted_links(
    main: Path,
    fb1: Path,
    fb2: Path,
    wants: Dict[Path, Path],
    file_system: FileSystemClientProtocol,
) -> None:
    """Remove unwanted symlinks and any real directories that conflict with wanted symlinks.

    Args:
        main: Main symlink path
        fb1: First fallback symlink path
        fb2: Second fallback symlink path
        wants: Mapping of link paths to their expected target paths
        file_system: File system client
    """
    for link in (main, fb1, fb2):
        if file_system.is_symlink(link) and link not in wants:
            file_system.unlink(link)
        # If link exists but is a real directory, remove it (regardless of whether it's wanted)
        # This handles the case where a real directory has the same name as a symlink that needs to be created
        elif file_system.exists(link) and not file_system.is_symlink(link):
            file_system.rmtree(link)


def compare_targets(
    current_target: Path, expected_target: Path, file_system: FileSystemClientProtocol
) -> bool:
    """Compare if two targets are the same by checking the resolved paths.

    Args:
        current_target: Currently resolved target path
        expected_target: Expected target path
        file_system: File system client

    Returns:
        True if targets match, False otherwise
    """
    try:
        resolved_current = file_system.resolve(current_target)
        resolved_expected = file_system.resolve(expected_target)
        return resolved_current == resolved_expected
    except OSError:
        # The target directory doesn't exist yet (common case)
        # We can't directly compare resolved paths, so return False to update the symlink
        return False


def handle_existing_symlink(
    link: Path, expected_target: Path, file_system: FileSystemClientProtocol
) -> None:
    """Handle an existing symlink to check if it points to the correct target.

    Args:
        link: Path to the existing symlink
        expected_target: Expected target path
        file_system: File system client
    """
    try:
        current_target = file_system.resolve(link)
        paths_match = compare_targets(current_target, expected_target, file_system)
        if paths_match:
            return  # already correct
        else:
            # Paths don't match, remove symlink to update to new target
            file_system.unlink(link)
    except OSError:
        # If resolve fails on the current symlink (broken symlink), remove it
        file_system.unlink(link)


def cleanup_existing_path_before_symlink(
    link: Path, expected_target: Path, file_system: FileSystemClientProtocol
) -> None:
    """Clean up existing path before creating a symlink.

    Args:
        link: Path where the symlink will be created
        expected_target: Expected target path
        file_system: File system client
    """
    # Double check: If link exists as a real directory, remove it before creating symlink
    if file_system.exists(link) and not file_system.is_symlink(link):
        file_system.rmtree(link)
    # If link is a symlink, check if it points to the correct target
    elif file_system.is_symlink(link):
        handle_existing_symlink(link, expected_target, file_system)

    # Final check: make sure there's nothing at link path before creating symlink
    if file_system.exists(link):
        # This should not happen with correct logic above, but for safety
        if file_system.is_symlink(link):
            file_system.unlink(link)
        else:
            file_system.rmtree(link)


def create_symlinks(
    main: Path,
    fb1: Path,
    fb2: Path,
    top_3: VersionCandidateList,
    file_system: FileSystemClientProtocol,
) -> bool:
    """Create symlinks for the top 3 Proton versions.

    Args:
        main: Main symlink path
        fb1: First fallback symlink path
        fb2: Second fallback symlink path
        top_3: List of top 3 (version, path) tuples
        file_system: File system client

    Returns:
        True if symlink creation was attempted (even if some failed)
    """
    # Create SymlinkSpec objects for all symlinks we want to create
    wanted_specs = create_symlink_specs(main, fb1, fb2, top_3)

    # Build a mapping from link path to target path
    wants: Dict[Path, Path] = {
        spec.link_path: spec.target_path for spec in wanted_specs
    }

    # First pass: Remove unwanted symlinks and any real directories that conflict with wanted symlinks
    cleanup_unwanted_links(main, fb1, fb2, wants, file_system)

    for link, target in wants.items():
        cleanup_existing_path_before_symlink(link, target, file_system)
        # Calculate relative path from the link location to the target for relative symlinks
        # If target is not in a subdirectory of link's parent, use absolute path
        try:
            relative_target = target.relative_to(link.parent)
        except ValueError:
            # If target is not a subpath of link.parent, use absolute path
            relative_target = target
        # Use target_is_directory=True to correctly handle directory symlinks
        try:
            file_system.symlink_to(link, relative_target, target_is_directory=True)
            logger.info("Created symlink %s -> %s", link.name, relative_target)
        except OSError as e:
            logger.error(
                "Failed to create symlink %s -> %s: %s", link.name, target.name, e
            )
            # Don't re-raise to handle gracefully as expected by test
            # The function should complete without crashing even if symlink creation fails
            continue  # Continue to the next link instead of failing the entire function

    return True
