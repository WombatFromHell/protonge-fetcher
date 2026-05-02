"""Link status queries for Proton installations.

Provides read-only functions to inspect the current state of symlinks
and determine whether they match expected targets.
"""

from pathlib import Path
from typing import Optional

from .common import FileSystemClientProtocol, ForkName, VersionCandidateList


def list_links(
    extract_dir: Path,
    fork: ForkName,
    file_system: FileSystemClientProtocol,
) -> dict[str, Optional[str]]:
    """List recognized symbolic links and their associated Proton fork folders.

    Args:
        extract_dir: Directory to search for links
        fork: The Proton fork name to determine link naming
        file_system: File system client

    Returns:
        Dictionary mapping link names to their target paths (or None if link doesn't exist)
    """
    link_names = _get_link_names(extract_dir, fork)

    links_info: dict[str, Optional[str]] = {}

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
    file_system: FileSystemClientProtocol,
) -> bool:
    """Check if a fork has any managed symbolic links.

    Args:
        extract_dir: Directory to search for links
        fork: The Proton fork name to determine link naming
        file_system: File system client

    Returns:
        True if at least one managed symlink exists for the fork, False otherwise
    """
    link_names = _get_link_names(extract_dir, fork)

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
    current_links: dict[str, Optional[str]],
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


def _get_link_names(
    extract_dir: Path,
    fork: ForkName,
) -> tuple[Path, Path, Path]:
    """Get the symlink names for the fork.

    Args:
        extract_dir: Directory where symlinks will be created
        fork: The Proton fork name

    Returns:
        Tuple of three Path objects: (main, fallback1, fallback2)
    """
    from .common import FORKS

    suffixes = FORKS[fork].link_names
    return (
        extract_dir / suffixes[0],
        extract_dir / suffixes[1],
        extract_dir / suffixes[2],
    )
