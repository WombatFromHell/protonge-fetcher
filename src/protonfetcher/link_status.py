"""Link status queries for Proton installations.

Provides read-only functions to inspect the current state of symlinks
and determine whether they match expected targets.
"""

from pathlib import Path
from typing import Mapping

from .common import (
    FileSystemClientProtocol,
    ForkName,
    VersionCandidateList,
)
from .dirs import get_link_names
from .version_finder import _deduplicate_candidates, find_version_candidates
from .filesystem import FileSystemClient


def get_installed_versions(
    extract_dir: Path,
    fork: ForkName,
    file_system: FileSystemClientProtocol | None = None,
) -> list[str]:
    """Get list of currently installed version tags for a fork.

    Finds all version directories for the specified fork and returns
    their tag names, sorted by version (newest first).
    """
    file_system = file_system or FileSystemClient()
    candidates = find_version_candidates(extract_dir, fork, file_system)

    if not candidates:
        return []

    candidates = _deduplicate_candidates(candidates)
    candidates.sort(key=lambda t: t[0], reverse=True)

    return [path.name for _, path in candidates]


def get_linked_versions(
    extract_dir: Path,
    fork: ForkName,
    file_system: FileSystemClientProtocol | None = None,
) -> set[str]:
    """Get set of version directories currently referenced by symlinks.

    Resolves all managed symlinks for the fork and returns the directory
    names they point to.
    """
    file_system = file_system or FileSystemClient()
    linked: set[str] = set()
    links_info = list_links(extract_dir, fork, file_system)

    for target_path in links_info.values():
        if target_path is not None:
            linked.add(Path(target_path).name)

    return linked


def list_links(
    extract_dir: Path,
    fork: ForkName,
    file_system: FileSystemClientProtocol | None = None,
) -> dict[str, str | None]:
    """List recognized symbolic links and their associated Proton fork folders.

    Args:
        extract_dir: Directory to search for links
        fork: The Proton fork name to determine link naming
        file_system: File system client

    Returns:
        Dictionary mapping link names to their target paths (or None if link doesn't exist)
    """
    file_system = file_system or FileSystemClient()
    link_names = get_link_names(extract_dir, fork)

    links_info: dict[str, str | None] = {}

    for link_path in link_names:
        if file_system.exists(link_path) and file_system.is_symlink(link_path):
            try:
                target_path = file_system.resolve(link_path)
                links_info[link_path.name] = str(target_path)
            except OSError:
                links_info[link_path.name] = None
        else:
            links_info[link_path.name] = None

    return links_info


def has_managed_links(
    extract_dir: Path,
    fork: ForkName,
    file_system: FileSystemClientProtocol | None = None,
) -> bool:
    """Check if a fork has any managed symbolic links.

    Args:
        extract_dir: Directory to search for links
        fork: The Proton fork name to determine link naming
        file_system: File system client

    Returns:
        True if at least one managed symlink exists for the fork, False otherwise
    """
    file_system = file_system or FileSystemClient()
    link_names = get_link_names(extract_dir, fork)

    for link_path in link_names:
        if file_system.exists(link_path) and file_system.is_symlink(link_path):
            return True

    return False


def build_expected_link_mapping(
    link_names: tuple[Path, Path, Path],
    top_3: VersionCandidateList,
) -> dict[str, str]:
    """Build expected link mapping from link names and top 3 candidates.

    Args:
        link_names: Tuple of (main, fb1, fb2) Path objects
        top_3: List of top 3 (version, path) tuples

    Returns:
        Dict mapping link name to expected target path
    """
    expected_links: dict[str, str] = {}
    for link_name, (version, target_path) in zip(link_names, top_3):
        expected_links[link_name.name] = str(target_path)
    return expected_links


def compare_link_targets(
    current_links: Mapping[str, str | None],
    expected_links: dict[str, str],
) -> bool:
    """Compare current vs expected link targets.

    Args:
        current_links: Dict mapping link name to current target path (or None)
        expected_links: Dict mapping link name to expected target path

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
