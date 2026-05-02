"""Candidate selection for Proton symlink management.

Extracts the logic for selecting top-3 version candidates from installed
Proton builds, handling both manual and regular release scenarios.
"""

import logging
from pathlib import Path
from typing import Optional

from .common import (
    ForkName,
    VersionCandidateList,
    VersionTuple,
)
from .utils import parse_version
from .version_finder import find_version_candidates

logger = logging.getLogger(__name__)


def select_top_3_candidates(
    extract_dir: Path,
    fork: ForkName,
    is_manual_release: bool,
    tag_dir: Optional[Path],
    file_system,
) -> Optional[VersionCandidateList]:
    """Get the top 3 version candidates for symlinks.

    Args:
        extract_dir: Directory containing Proton installations
        fork: The Proton fork name
        is_manual_release: Whether this is a manual release
        tag_dir: Path to the manual release directory (if applicable)
        file_system: File system client

    Returns:
        List of top 3 (version, path) tuples, or None if no candidates found
    """
    candidates = find_version_candidates(extract_dir, fork, file_system)
    if not candidates:
        return None

    candidates = _deduplicate_candidates(candidates)

    if is_manual_release and tag_dir is not None:
        top_3 = select_manual_release_candidates(fork, candidates, tag_dir)
    else:
        top_3 = select_regular_release_candidates(candidates)

    if not top_3:
        return None

    return top_3


def select_manual_release_candidates(
    fork: ForkName,
    candidates: VersionCandidateList,
    tag_dir: Path,
) -> VersionCandidateList:
    """Handle candidates for manual releases.

    Adds the manual tag to candidates and returns top 3.

    Args:
        fork: The Proton fork name
        candidates: List of existing version candidates
        tag_dir: Path to the manual release directory

    Returns:
        Top 3 (version, path) tuples including the manual release
    """
    tag_version = parse_version(tag_dir.name, fork)

    # Check if this version is already in candidates to avoid duplicates
    existing_versions: set[VersionTuple] = {candidate[0] for candidate in candidates}
    if tag_version not in existing_versions:
        candidates.append((tag_version, tag_dir))

    # Sort all candidates including the manual tag
    candidates.sort(key=lambda t: t[0], reverse=True)

    # Take top 3
    top_3: list[tuple[VersionTuple, Path]] = candidates[:3]
    return top_3


def select_regular_release_candidates(
    candidates: VersionCandidateList,
) -> VersionCandidateList:
    """Handle candidates for regular releases.

    Args:
        candidates: List of version candidates

    Returns:
        Top 3 (version, path) tuples sorted newest first
    """
    candidates.sort(key=lambda t: t[0], reverse=True)
    top_3: VersionCandidateList = candidates[:3]
    return top_3


def _deduplicate_candidates(
    candidates: VersionCandidateList,
) -> VersionCandidateList:
    """Remove duplicate versions, preferring standard naming.

    Args:
        candidates: List of (version, path) tuples

    Returns:
        Deduplicated list of candidates
    """
    seen: set[VersionTuple] = set()
    result: VersionCandidateList = []
    for version, path in candidates:
        if version not in seen:
            seen.add(version)
            result.append((version, path))
    return result
