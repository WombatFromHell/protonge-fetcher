"""Version discovery and deduplication for Proton installations.

Scans a directory for Proton build directories, parses their versions,
filters by fork, and deduplicates candidates.
"""

import logging
import re
from pathlib import Path

from .common import (
    FORKS,
    FileSystemClientProtocol,
    ForkName,
    VersionCandidateList,
    VersionGroups,
    VersionTuple,
)
from .utils import parse_version
from .filesystem import FileSystemClient

logger = logging.getLogger(__name__)


def _get_tag_name(entry: Path, fork: ForkName) -> str:
    """Strip the fork-specific prefix/suffix to get the parseable tag name."""
    name = entry.name
    if fork == ForkName.PROTON_EM:
        return name.removeprefix("proton-")
    if fork == ForkName.CACHYOS:
        return name.removeprefix("proton-").removesuffix("-x86_64")
    if fork == ForkName.DW_PROTON:
        return name.removesuffix("-x86_64")
    return name


def _should_skip_directory(tag_name: str, fork: ForkName) -> bool:
    """Check if directory should be skipped based on fork skip prefixes.

    Args:
        tag_name: The cleaned tag name
        fork: The Proton fork name

    Returns:
        True if the directory should be skipped
    """
    for prefix in FORKS[fork].skip_prefixes:
        if tag_name.startswith(prefix):
            return True
    return False


def _is_valid_proton_directory(entry: Path, fork: ForkName) -> bool:
    """Validate that the directory name matches a naming pattern for the fork.

    Args:
        entry: Directory path to validate
        fork: The Proton fork name

    Returns:
        True if the directory matches one of the fork's naming patterns
    """
    return any(
        re.match(pattern, entry.name) is not None
        for pattern in FORKS[fork].dir_name_patterns
    )


def find_version_candidates(
    extract_dir: Path,
    fork: ForkName,
    file_system: FileSystemClientProtocol | None = None,
) -> VersionCandidateList:
    """Find all directories that look like Proton builds and parse their versions.

    Scans the extract directory, filters by fork-specific patterns, parses
    version numbers, and returns a list of (version_tuple, path) tuples.

    Args:
        extract_dir: Base directory to search
        fork: The Proton fork name
        file_system: File system client for directory iteration

    Returns:
        List of (version_tuple, directory_path) tuples
    """
    file_system = file_system or FileSystemClient()
    candidates: list[tuple[VersionTuple, Path]] = []
    for entry in file_system.iterdir(extract_dir):
        if file_system.is_dir(entry) and not file_system.is_symlink(entry):
            tag_name = _get_tag_name(entry, fork)

            if _should_skip_directory(tag_name, fork):
                continue

            if _is_valid_proton_directory(entry, fork):
                candidates.append((parse_version(tag_name, fork), entry))
    return candidates


def _deduplicate_candidates(candidates: VersionCandidateList) -> VersionCandidateList:
    """Remove duplicate versions, preferring directories with standard naming.

    Groups candidates by parsed version and selects the preferred directory
    (prefers names without 'proton-' prefix, shorter names, alphabetical).

    Args:
        candidates: List of (version_tuple, path) tuples, possibly with duplicates

    Returns:
        Deduplicated list with one entry per unique version
    """
    version_groups: VersionGroups = {}
    for parsed_version, directory_path in candidates:
        if parsed_version not in version_groups:
            version_groups[parsed_version] = []
        version_groups[parsed_version].append(directory_path)

    unique_candidates: VersionCandidateList = []
    for parsed_version, directories in version_groups.items():
        preferred_dir = min(
            directories,
            key=lambda d: (
                1 if d.name.startswith("proton-") else 0,
                len(d.name),
                d.name,
            ),
        )
        unique_candidates.append((parsed_version, preferred_dir))

    return unique_candidates
