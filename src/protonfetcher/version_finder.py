"""Version discovery and deduplication for Proton installations.

Scans a directory for Proton build directories, parses their versions,
filters by fork, and deduplicates candidates.
"""

from __future__ import annotations

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

logger = logging.getLogger(__name__)


def _get_tag_name(entry: Path, fork: ForkName) -> str:
    """Get the tag name from the directory entry, handling fork-specific prefixes.

    Args:
        entry: Directory path to parse
        fork: The Proton fork name

    Returns:
        Cleaned tag name suitable for version parsing
    """
    if fork == ForkName.PROTON_EM and entry.name.startswith("proton-"):
        return entry.name[7:]  # Remove "proton-" prefix
    elif fork == ForkName.CACHYOS and entry.name.startswith("proton-"):
        # Remove "proton-" prefix and "-x86_64" suffix if present
        name = entry.name[7:]  # Remove "proton-" prefix
        if name.endswith("-x86_64"):
            name = name[:-7]  # Remove "-x86_64" suffix
        return name
    elif fork == ForkName.DW_PROTON and entry.name.endswith("-x86_64"):
        # Remove "-x86_64" suffix for DW-Proton
        return entry.name[:-7]
    else:
        return entry.name


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
    """Validate that the directory name matches expected pattern for the fork.

    Args:
        entry: Directory path to validate
        fork: The Proton fork name

    Returns:
        True if the directory matches the fork's naming pattern
    """
    match fork:
        case ForkName.GE_PROTON:
            ge_pattern = r"^GE-Proton\d+-\d+(?:-.*)?$"
            return bool(re.match(ge_pattern, entry.name))
        case ForkName.PROTON_EM:
            em_pattern1 = r"^proton-EM-\d+\.\d+-\d+(?:-.*)?$"
            em_pattern2 = r"^EM-\d+\.\d+-\d+(?:-.*)?$"
            return bool(
                re.match(em_pattern1, entry.name) or re.match(em_pattern2, entry.name)
            )
        case ForkName.CACHYOS:
            cachyos_pattern1 = r"^proton-cachyos-\d+\.\d+-\d+-slr(?:-x86_64)?(?:-.*)?$"
            cachyos_pattern2 = r"^cachyos-\d+\.\d+-\d+-slr(?:-.*)?$"
            return bool(
                re.match(cachyos_pattern1, entry.name)
                or re.match(cachyos_pattern2, entry.name)
            )
        case ForkName.DW_PROTON:
            dwproton_pattern = r"^dwproton-\d+\.\d+-\d+-x86_64(?:-.*)?$"
            return bool(re.match(dwproton_pattern, entry.name))


def find_version_candidates(
    extract_dir: Path,
    fork: ForkName,
    file_system: FileSystemClientProtocol,
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
