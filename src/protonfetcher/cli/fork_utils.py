"""Fork-related utilities for the CLI.

Extracted from cli.py to centralize fork conversion and dispatch logic.
"""

import logging
from pathlib import Path
from typing import Any, Union

from protonfetcher.common import DEFAULT_FORK, FORKS, ForkName
from protonfetcher.forgejo_fetcher import ForgejoReleaseFetcher
from protonfetcher.github_fetcher import GitHubReleaseFetcher

logger = logging.getLogger(__name__)


def convert_fork_to_enum(fork_arg: Union[str, ForkName, None]) -> ForkName:
    """Convert fork argument to ForkName enum."""
    if isinstance(fork_arg, str):
        try:
            return ForkName(fork_arg)
        except ValueError:
            print(f"Error: Invalid fork '{fork_arg}'")
            raise SystemExit(1) from None
    elif fork_arg is None:
        return DEFAULT_FORK
    else:
        return fork_arg


def get_fork_from_args(args: Any) -> ForkName | None:
    """Extract fork from args, returning None if not provided.

    Handles the hasattr + None check boilerplate that appears throughout handlers.
    """
    if hasattr(args, "fork") and args.fork is not None:
        return convert_fork_to_enum(args.fork)
    return None


def get_forks_to_list(args: Any, list_all_forks: bool) -> list[ForkName]:
    """Determine which forks to list based on arguments."""
    if list_all_forks or (not hasattr(args, "fork") or args.fork is None):
        return list(FORKS.keys())
    fork_enum = convert_fork_to_enum(args.fork)
    return [fork_enum]


def get_fork_fetcher(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    fork: ForkName,
):
    """Return the appropriate fetcher for the given fork."""
    if fork == ForkName.DW_PROTON:
        return forgejo_fetcher
    return fetcher


def print_prunable_versions(
    link_manager: Any, extract_dir: Path, fork: ForkName
) -> None:
    """Print prunable versions for a fork (installed but not linked)."""
    installed = link_manager.get_installed_versions(extract_dir, fork)
    linked = link_manager.get_linked_versions(extract_dir, fork)
    prunable = [v for v in installed if v not in linked]
    if prunable:
        print(f"\nPrunable {fork.value} versions ({len(prunable)}):")
        for version in prunable:
            print(f"  ○ {version}")


def print_links_for_fork(
    link_manager: Any, extract_dir: Path, fork: ForkName, show_versions: bool = False
) -> bool:
    """Print links for a single fork.

    Returns:
        True if the fork had symlinks or prunable versions (was printed).
    """
    links_info = link_manager.list_links(extract_dir, fork)
    has_symlinks = any(target_path for target_path in links_info.values())

    if show_versions:
        installed = link_manager.get_installed_versions(extract_dir, fork)
        linked = link_manager.get_linked_versions(extract_dir, fork)
        prunable = [v for v in installed if v not in linked]
    else:
        prunable = []

    if not has_symlinks and not prunable:
        return False

    print(f"Links for {fork.value}:")
    for link_name, target_path in links_info.items():
        if target_path:
            print(f"  {link_name} -> {target_path}")
        else:
            print(f"  {link_name} -> (not found)")

    if prunable:
        print(f"\nPrunable {fork.value} versions ({len(prunable)}):")
        for version in prunable:
            print(f"  ○ {version}")

    return True


def get_link_names_for_fork(
    extract_dir: Path, fork: ForkName
) -> tuple[Path, Path, Path]:
    """Get the symlink paths for a given fork.

    Args:
        extract_dir: Base directory for symlinks
        fork: The Proton fork name

    Returns:
        Tuple of (main, fb1, fb2) Path objects
    """
    suffixes = FORKS[fork].link_names
    return (
        extract_dir / suffixes[0],
        extract_dir / suffixes[1],
        extract_dir / suffixes[2],
    )
