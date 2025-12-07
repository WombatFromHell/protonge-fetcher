"""Utility functions for ProtonFetcher."""

import re

from .common import ForkName


def parse_version(
    tag: str, fork: ForkName = ForkName.GE_PROTON
) -> tuple[str, int, int, int]:
    """
    Parse a version tag to extract the numeric components for comparison.

    Args:
        tag: The release tag (e.g., 'GE-Proton10-20' or 'EM-10.0-30')
        fork: The fork name to determine parsing logic

    Returns:
        A tuple of (prefix, major, minor, patch) for comparison purposes, or a fallback tuple if parsing fails
    """
    match fork:
        case ForkName.PROTON_EM:
            # Proton-EM format: EM-10.0-30 -> prefix="EM", major=10, minor=0, patch=30
            pattern = r"EM-(\d+)\.(\d+)-(\d+)"
            match_result = re.match(pattern, tag)
            if match_result:
                major, minor, patch = map(int, match_result.groups())
                return ("EM", major, minor, patch)
            # If no match, return a tuple that will put this tag at the end for comparison
            return (tag, 0, 0, 0)
        case ForkName.GE_PROTON:
            # GE-Proton format: GE-Proton10-20 -> prefix="GE-Proton", major=10, minor=20
            pattern = r"GE-Proton(\d+)-(\d+)"
            match_result = re.match(pattern, tag)
            if match_result:
                major, minor = map(int, match_result.groups())
                # For GE-Proton, we treat the minor as a patch-like value for comparison
                return ("GE-Proton", major, 0, minor)
            # If no match, return a tuple that will put this tag at the end for comparison
            return (tag, 0, 0, 0)
        case _:
            # If unexpected fork value, return a tuple that will put this tag at the end for comparison
            return (tag, 0, 0, 0)


def compare_versions(tag1: str, tag2: str, fork: ForkName = ForkName.GE_PROTON) -> int:
    """
    Compare two version tags to determine which is newer.

    Args:
        tag1: First tag to compare
        tag2: Second tag to compare
        fork: The fork name to determine parsing logic

    Returns:
        -1 if tag1 is older than tag2, 0 if equal, 1 if tag1 is newer than tag2
    """
    p1_prefix, p1_major, p1_minor, p1_patch = parse_version(tag1, fork)
    p2_prefix, p2_major, p2_minor, p2_patch = parse_version(tag2, fork)

    if (p1_prefix, p1_major, p1_minor, p1_patch) == (
        p2_prefix,
        p2_major,
        p2_minor,
        p2_patch,
    ):
        return 0

    # Compare component by component
    if p1_prefix < p2_prefix:
        return -1
    elif p1_prefix > p2_prefix:
        return 1

    if p1_major < p2_major:
        return -1
    elif p1_major > p2_major:
        return 1

    if p1_minor < p2_minor:
        return -1
    elif p1_minor > p2_minor:
        return 1

    if p1_patch < p2_patch:
        return -1
    elif p1_patch > p2_patch:
        return 1

    return 0  # If all components are equal


def get_proton_asset_name(tag: str, fork: ForkName = ForkName.GE_PROTON) -> str:
    """
    Generate the expected Proton asset name from a tag and fork.

    Args:
        tag: The release tag (e.g., 'GE-Proton10-20' for GE-Proton, 'EM-10.0-30' for Proton-EM)
        fork: The fork name (default: 'GE-Proton')

    Returns:
        The expected asset name (e.g., 'GE-Proton10-20.tar.gz' or 'proton-EM-10.0-30.tar.xz')
    """
    if fork == ForkName.PROTON_EM:
        # For Proton-EM, the asset name follows pattern: proton-<tag>.tar.xz
        # e.g., tag 'EM-10.0-30' becomes 'proton-EM-10.0-30.tar.xz'
        return f"proton-{tag}.tar.xz"
    else:
        # For GE-Proton, the asset name follows pattern: <tag>.tar.gz
        # e.g., tag 'GE-Proton10-20' becomes 'GE-Proton10-20.tar.gz'
        return f"{tag}.tar.gz"


def format_bytes(bytes_value: int) -> str:
    """Format bytes into a human-readable string."""
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.2f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.2f} GB"
