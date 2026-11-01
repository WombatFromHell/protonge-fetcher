"""Utility functions for ProtonFetcher."""

import errno
import re
from pathlib import Path

from .common import FORKS, ForkName

# errno -> the phrase a user can act on; anything unlisted keeps the
# original OSError detail, which is already specific.
_ERRNO_HINTS: dict[int, str] = {
    errno.ENOENT: "does not exist",
    errno.ENOTDIR: "not a directory",
    errno.EEXIST: "already exists",
    errno.EISDIR: "is a directory",
    errno.EACCES: "permission denied",
    errno.EPERM: "operation not permitted",
    errno.ENOSPC: "no space left on device",
    errno.EROFS: "read-only filesystem",
    errno.ENOTEMPTY: "directory not empty",
    errno.ELOOP: "too many levels of symbolic links",
    errno.ENAMETOOLONG: "name too long",
    errno.EFBIG: "file too large",
    errno.EINVAL: "invalid argument",
    errno.ETIMEDOUT: "timed out",
    errno.ECONNRESET: "connection reset by peer",
    errno.ECONNABORTED: "connection aborted",
}


def errno_hint(error: OSError) -> str:
    """Plain-English reason for an OSError, e.g. 'permission denied'."""
    hint = _ERRNO_HINTS.get(error.errno) if error.errno is not None else None
    return hint or str(error)


def describe_os_error(action: str, path: Path | str, error: OSError) -> str:
    """Plain-English description of a failed filesystem operation."""
    return f"Failed to {action} {path}: {errno_hint(error)}"


def friendly_os_error(action: str, path: Path | str, error: OSError) -> OSError:
    """The same OSError type, re-worded, with its errno intact.

    Type and errno are preserved because callers guard on FileNotFoundError,
    FileExistsError and OSError and errno_hint() reads errno. filename is not
    copied: the path is already in the message.
    """
    message = describe_os_error(action, path, error)
    if error.errno is None:
        return type(error)(message)
    return type(error)(error.errno, message)


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
            # Proton-GE: (major, minor) → (prefix, major, 0, minor)
            major, minor = groups
            return (prefix, major, 0, minor)
        else:
            # Others: (major, minor, patch) → (prefix, major, minor, patch)
            major, minor, patch = groups
            return (prefix, major, minor, patch)
    # If no match, return a tuple that will put this tag at the end for comparison
    return (tag, 0, 0, 0)


def get_proton_asset_name(tag: str, fork: ForkName = ForkName.GE_PROTON) -> str:
    """
    Generate the expected Proton asset name from a tag and fork.

    Args:
        tag: The release tag (e.g., 'GE-Proton10-20' for Proton-GE, 'EM-10.0-30' for Proton-EM)
        fork: The fork name (default: 'Proton-GE')

    Returns:
        The expected asset name (e.g., 'GE-Proton10-20.tar.gz' or 'proton-EM-10.0-30.tar.xz')
    """
    cfg = FORKS.get(fork)
    template = cfg.asset_template if cfg else "{tag}.tar.gz"
    return template.format(tag=tag)


def format_bytes(bytes_value: int) -> str:
    """Format bytes into a human-readable string using binary units (KiB, MiB, GiB)."""
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.2f} KiB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.2f} MiB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.2f} GiB"


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
