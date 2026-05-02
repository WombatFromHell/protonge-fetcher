"""Utility functions for ProtonFetcher."""

import re
from typing import Type

from .common import FORKS, ForkName


def validate_protocol_instance(obj: object, protocol: Type) -> bool:
    """Validate that an object implements a protocol at runtime.

    This utility function checks if an object conforms to a given protocol by verifying
    that all required methods and attributes are present and have the correct types.
    Useful for debugging and testing protocol implementations during development.

    Args:
        obj: Object to validate
        protocol: Protocol class to validate against

    Returns:
        True if object implements the protocol, False otherwise

    Example:
        >>> from protonfetcher.common import NetworkClientProtocol
        >>> from protonfetcher.network import NetworkClient
        >>> client = NetworkClient(timeout=30)
        >>> validate_protocol_instance(client, NetworkClientProtocol)
        True

    Note:
        This is a runtime validation utility and should not be used in production
        performance-critical code. It's primarily intended for debugging and testing.
    """
    try:
        # Check if all protocol methods and attributes are present
        for attr_name in dir(protocol):
            if attr_name.startswith("_"):
                continue

            attr = getattr(protocol, attr_name)

            if callable(attr):
                # It's a method - check if object has callable with same name
                obj_attr = getattr(obj, attr_name, None)
                if not callable(obj_attr):
                    return False
            else:
                # It's an attribute - check if object has it
                if not hasattr(obj, attr_name):
                    return False
        return True
    except Exception:
        return False


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
    cfg = FORKS.get(fork)
    if cfg is None:
        pattern, prefix, is_ge_proton = r"", tag, False
    else:
        pattern, prefix, is_ge_proton = (
            cfg.version_pattern,
            cfg.version_prefix,
            cfg.is_ge_proton,
        )
    match_result = re.match(pattern, tag)
    if match_result:
        groups = list(map(int, match_result.groups()))
        if is_ge_proton:
            # GE-Proton: (major, minor) → (prefix, major, 0, minor)
            major, minor = groups
            return (prefix, major, 0, minor)
        else:
            # Others: (major, minor, patch) → (prefix, major, minor, patch)
            major, minor, patch = groups
            return (prefix, major, minor, patch)
    # If no match, return a tuple that will put this tag at the end for comparison
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
    v1 = parse_version(tag1, fork)
    v2 = parse_version(tag2, fork)
    return (v1 > v2) - (v1 < v2)


def get_proton_asset_name(tag: str, fork: ForkName = ForkName.GE_PROTON) -> str:
    """
    Generate the expected Proton asset name from a tag and fork.

    Args:
        tag: The release tag (e.g., 'GE-Proton10-20' for GE-Proton, 'EM-10.0-30' for Proton-EM)
        fork: The fork name (default: 'GE-Proton')

    Returns:
        The expected asset name (e.g., 'GE-Proton10-20.tar.gz' or 'proton-EM-10.0-30.tar.xz')
    """
    cfg = FORKS.get(fork)
    template = cfg.asset_template if cfg else "{tag}.tar.gz"
    return template.format(tag=tag)


def format_size(bytes_value: int) -> str:
    """Format bytes into a human-readable string using binary units (KiB, MiB, GiB)."""
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.2f} KiB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.2f} MiB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.2f} GiB"


# Backward-compat alias
format_bytes = format_size


def format_rate(bytes_per_sec: float) -> str:
    """Format a byte rate using binary units (KiB/s, MiB/s, GiB/s)."""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.2f} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.2f} KiB/s"
    elif bytes_per_sec < 1024 * 1024 * 1024:
        return f"{bytes_per_sec / (1024 * 1024):.2f} MiB/s"
    else:
        return f"{bytes_per_sec / (1024 * 1024 * 1024):.2f} GiB/s"
