"""Release removal operations for Proton installations.

Provides functions to remove specific Proton releases and their
associated symbolic links.
"""

import logging
from pathlib import Path

from .common import FileSystemClientProtocol, ForkName
from .exceptions import LinkManagementError

logger = logging.getLogger(__name__)


def remove_release(
    extract_dir: Path,
    tag: str,
    fork: ForkName,
    file_system: FileSystemClientProtocol,
) -> bool:
    """Remove a specific Proton fork release folder and its associated symbolic links.

    Args:
        extract_dir: Directory containing the release folder
        tag: The release tag to remove
        fork: The Proton fork name to determine link naming
        file_system: File system client

    Returns:
        True if the removal was successful

    Raises:
        LinkManagementError: If the release directory does not exist
    """
    release_path = _determine_release_path(extract_dir, tag, fork, file_system)

    # Check if the release directory exists
    _check_release_exists(release_path, file_system)

    # Identify links that point to this release directory
    links_to_remove = _identify_links_to_remove(
        extract_dir, release_path, fork, file_system
    )

    # Remove the release directory
    _remove_release_directory(release_path, file_system)

    # Remove the associated symbolic links that point to this release
    _remove_symbolic_links(links_to_remove, file_system)

    return True


def _determine_release_path(
    extract_dir: Path,
    tag: str,
    fork: ForkName,
    file_system: FileSystemClientProtocol,
) -> Path:
    """Determine the correct release path using fork-specific templates."""
    from .link_manager import resolve_directory

    return resolve_directory(extract_dir, tag, fork, file_system)


def _check_release_exists(
    release_path: Path, file_system: FileSystemClientProtocol
) -> None:
    """Check if the release directory exists, raise error if not.

    Args:
        release_path: Path to check
        file_system: File system client

    Raises:
        LinkManagementError: If the directory does not exist
    """
    if not file_system.exists(release_path):
        raise LinkManagementError(f"Release directory does not exist: {release_path}")


def _identify_links_to_remove(
    extract_dir: Path,
    release_path: Path,
    fork: ForkName,
    file_system: FileSystemClientProtocol,
) -> list[Path]:
    """Identify symbolic links that point to the release directory.

    Args:
        extract_dir: Directory containing the links
        release_path: Path of the release to find links for
        fork: The Proton fork name to determine link naming
        file_system: File system client

    Returns:
        List of Path objects pointing to the release
    """
    from .common import FORKS

    suffixes = FORKS[fork].link_names
    links_to_remove: list[Path] = []

    for suffix in suffixes:
        link_path = extract_dir / suffix

        if not file_system.is_symlink(link_path):
            continue

        try:
            resolved = file_system.resolve(link_path)
            if resolved == release_path:
                links_to_remove.append(link_path)
        except OSError:
            # Broken symlink — still remove it
            links_to_remove.append(link_path)

    return links_to_remove


def _remove_release_directory(
    release_path: Path,
    file_system: FileSystemClientProtocol,
) -> None:
    """Remove the release directory.

    Args:
        release_path: Path of the directory to remove
        file_system: File system client

    Raises:
        LinkManagementError: If the directory cannot be removed
    """
    try:
        file_system.rmtree(release_path)
        logger.info("Removed release directory: %s", release_path)
    except Exception as e:
        raise LinkManagementError(
            f"Failed to remove release directory {release_path}: {e}"
        )


def _remove_symbolic_links(
    links_to_remove: list[Path],
    file_system: FileSystemClientProtocol,
) -> None:
    """Remove the associated symbolic links.

    Args:
        links_to_remove: List of symlink paths to remove
        file_system: File system client
    """
    for link in links_to_remove:
        try:
            file_system.unlink(link)
            logger.info("Removed symbolic link: %s", link)
        except Exception as e:
            logger.error("Failed to remove symbolic link %s: %s", link, e)
