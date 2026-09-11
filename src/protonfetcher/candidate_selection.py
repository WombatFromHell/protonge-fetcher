"""Candidate selection for Proton symlink management.

Extracts the logic for selecting top-3 version candidates from installed
Proton builds, handling both manual and regular release scenarios.
"""

import logging
from pathlib import Path

from .common import (
    ForkName,
    VersionCandidateList,
)
from .utils import parse_version
from .version_finder import _deduplicate_candidates, find_version_candidates

logger = logging.getLogger(__name__)


def select_top_3_candidates(
    extract_dir: Path,
    fork: ForkName,
    tag_dir: Path | None,
    file_system,
) -> VersionCandidateList | None:
    """Get the top 3 version candidates for symlinks.

    Args:
        extract_dir: Directory containing Proton installations
        fork: The Proton fork name
        tag_dir: A release directory to force into the candidate list before
            ranking (a manual release, or a not-yet-extracted dir in dry-run).
        file_system: File system client

    Returns:
        List of top 3 (version, path) tuples, or None if no candidates found
    """
    candidates = find_version_candidates(extract_dir, fork, file_system)

    # Force the tag directory into the candidate list before ranking
    if tag_dir is not None:
        tag_version = parse_version(tag_dir.name, fork)
        if tag_version not in {c[0] for c in candidates}:
            candidates.append((tag_version, tag_dir))

    if not candidates:
        return None

    candidates = _deduplicate_candidates(candidates)
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[:3]
