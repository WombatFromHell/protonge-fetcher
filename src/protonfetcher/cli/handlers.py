"""Operation handlers for the CLI.

Extracted from cli.py to make handlers importable and testable independently.
"""

import logging
from pathlib import Path
from typing import Any

from protonfetcher.common import DEFAULT_FORK, FORKS, ForkName
from protonfetcher.exceptions import ProtonFetcherError
from protonfetcher.forgejo_fetcher import ForgejoReleaseFetcher
from protonfetcher.github_fetcher import GitHubReleaseFetcher

from .fork_utils import (
    get_fork_fetcher,
    get_fork_from_args,
    get_link_names_for_fork,
    print_success,
)

logger = logging.getLogger(__name__)


def handle_ls_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: Any,
    extract_dir: Path,
    list_all_forks: bool = False,
) -> None:
    """Handle the --ls operation to list symbolic links."""
    from .fork_utils import get_forks_to_list, print_links_for_fork

    print("Listing recognized links and their associated Proton fork folders...")
    forks_to_check = get_forks_to_list(args, list_all_forks)
    for fork in forks_to_check:
        lm = get_fork_fetcher(fetcher, forgejo_fetcher, fork).link_manager
        print_links_for_fork(lm, extract_dir, fork, show_versions=True)
    print("Success")


def handle_list_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: Any,
    extract_dir: Path,
) -> None:
    """Handle the --list operation flow."""
    target_fork: ForkName = get_fork_from_args(args) or DEFAULT_FORK
    repo = FORKS[target_fork].repo
    logger.info(f"Using fork: {target_fork} ({repo})")

    fetcher_for_fork = get_fork_fetcher(fetcher, forgejo_fetcher, target_fork)
    tags = fetcher_for_fork.list_recent_releases(repo)
    print("Recent releases:")
    for tag in tags:
        print(f"  {tag}")
    print_success()


def handle_relink_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: Any,
    extract_dir: Path,
) -> None:
    """Handle the --relink operation flow."""
    relink_fork = get_fork_from_args(args) or DEFAULT_FORK
    logger.info(f"Relinking {relink_fork} symlinks")
    fork_fetcher = get_fork_fetcher(fetcher, forgejo_fetcher, relink_fork)
    fork_fetcher.relink_fork(extract_dir, relink_fork)
    print_success()


def _remove_all_fork_symlinks(
    extract_dir: Path,
    fork: ForkName,
    link_manager,
) -> None:
    """Remove all managed symlinks for a given fork."""

    main, fb1, fb2 = get_link_names_for_fork(extract_dir, fork)
    for link in (main, fb1, fb2):
        if link.exists() or link.is_symlink():
            try:
                link.unlink()
                logger.info(f"Removed symlink: {link}")
            except OSError as e:
                logger.warning(f"Failed to remove symlink {link}: {e}")


def _cleanup_stale_symlinks(
    extract_dir: Path,
    fork: ForkName,
    link_manager,
) -> None:
    """Remove dangling symlinks and update stale ones.

    Delegates to release_operations.cleanup_stale_symlinks.
    """
    from protonfetcher.filesystem import FileSystemClient
    from protonfetcher.release_operations import cleanup_stale_symlinks as _cleanup

    _cleanup(extract_dir, fork, FileSystemClient())


def handle_rm_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: Any,
    extract_dir: Path,
) -> None:
    """Handle the --rm operation flow.

    Two modes:
    - --rm <tag>: remove that specific release directory + its symlinks
    - --rm --fork <fork>: remove ALL symlinks for that fork
    """
    rm_fork = get_fork_from_args(args) or DEFAULT_FORK
    fork_fetcher = get_fork_fetcher(fetcher, forgejo_fetcher, rm_fork)

    if args.rm:
        # Remove a specific release by tag
        logger.info(f"Removing release: {args.rm}")
        fork_fetcher.link_manager.remove_release(extract_dir, args.rm, rm_fork)
        print(f"Removed {args.rm}")
    else:
        # Remove all symlinks for the fork
        logger.info(f"Removing all symlinks for {rm_fork}")
        _remove_all_fork_symlinks(extract_dir, rm_fork, fork_fetcher.link_manager)
        print(f"Removed all symlinks for {rm_fork}")

    # Always clean up dangling/stale symlinks after removal
    _cleanup_stale_symlinks(extract_dir, rm_fork, fork_fetcher.link_manager)
    print_success()


def _collect_prune_candidates(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    extract_dir: Path,
    forks: list[ForkName],
    keep: int,
) -> dict[ForkName, list[str]]:
    """Scan forks and return a mapping of fork → list of versions to prune."""
    all_to_prune: dict[ForkName, list[str]] = {}
    for fork in forks:
        fork_fetcher = get_fork_fetcher(fetcher, forgejo_fetcher, fork)
        _, to_prune = fork_fetcher.prune_releases(
            extract_dir, fork, keep=keep, dry_run=True
        )
        all_to_prune[fork] = to_prune
    return all_to_prune


def _confirm_prune(total_count: int) -> bool:
    """Prompt the user for confirmation. Returns True if confirmed."""
    print(
        "⚠️  WARNING: Pruning old releases may break Steam prefixes that depend on them."
    )
    print("Games using pruned versions will need to be reconfigured.")

    try:
        response = (
            input(f"\nProceed with pruning {total_count} release(s)? [y/N]: ")
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        print("\nAborted")
        raise SystemExit(1) from None

    if response not in ("y", "yes"):
        print("Aborted")
        raise SystemExit(0)
    return True


def _execute_prune(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    extract_dir: Path,
    forks: list[ForkName],
    keep: int,
    to_prune: dict[ForkName, list[str]],
) -> int:
    """Execute the actual pruning across forks. Returns total count pruned."""
    total_pruned = 0
    for fork in forks:
        if to_prune[fork]:
            logger.info(f"Pruning old {fork.value} releases...")
            fork_fetcher = get_fork_fetcher(fetcher, forgejo_fetcher, fork)
            _, pruned = fork_fetcher.prune_releases(
                extract_dir, fork, keep=keep, dry_run=False
            )
            total_pruned += len(pruned)
    return total_pruned


def handle_prune_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: Any,
    extract_dir: Path,
) -> None:
    """Handle the --prune operation flow."""
    explicit_fork = get_fork_from_args(args)
    forks_to_prune = [explicit_fork] if explicit_fork else list(FORKS.keys())

    all_to_prune = _collect_prune_candidates(
        fetcher, forgejo_fetcher, extract_dir, forks_to_prune, args.keep
    )

    total_to_prune = sum(len(v) for v in all_to_prune.values())
    if total_to_prune == 0:
        print("No unmanaged releases to prune")
        print("Success")
        return

    print(f"\nWould prune {total_to_prune} old version(s):")
    for fork in forks_to_prune:
        for version in all_to_prune[fork]:
            print(f"  ○ {version}")
    print()

    if args.dry_run:
        print("Dry run complete - no changes made")
        print("Success")
        return

    _confirm_prune(total_to_prune)

    total_pruned = _execute_prune(
        fetcher, forgejo_fetcher, extract_dir, forks_to_prune, args.keep, all_to_prune
    )

    print(f"\nPruned {total_pruned} release(s)")
    print("Success")


def _check_single_fork(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    extract_dir: Path,
    fork: ForkName,
    check_managed_only: bool,
) -> bool:
    """Check for updates on a single fork. Returns True if update available."""
    if check_managed_only:
        lm = get_fork_fetcher(fetcher, forgejo_fetcher, fork).link_manager
        if not lm.has_managed_links(extract_dir, fork):
            logger.debug(f"Skipping {fork}: no managed links found")
            return False

    try:
        fork_fetcher = get_fork_fetcher(fetcher, forgejo_fetcher, fork)
        newer_release = fork_fetcher.check_for_updates(extract_dir, fork)
    except ProtonFetcherError as e:
        logger.error(f"Failed to check {fork}: {e}")
        return False

    if newer_release:
        print(f"New release available for {fork}: {newer_release}!")
        return True
    print(f"{fork}: up-to-date")
    return False


def handle_check_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: Any,
    extract_dir: Path,
) -> None:
    """Handle the --check operation flow."""
    explicit_fork = get_fork_from_args(args)
    if explicit_fork:
        forks_to_check = [explicit_fork]
        check_managed_only = False
    else:
        forks_to_check = list(FORKS.keys())
        check_managed_only = True

    updates_available = any(
        _check_single_fork(
            fetcher, forgejo_fetcher, extract_dir, fork, check_managed_only
        )
        for fork in forks_to_check
    )

    if updates_available:
        raise SystemExit(0)
    raise SystemExit(1)


def handle_default_fetch(
    fetcher: GitHubReleaseFetcher,
    repo: str,
    output_dir: Path,
    extract_dir: Path,
    args: Any,
) -> None:
    """Handle the default fetch and extract operation flow (GitHub forks only)."""
    actual_fork = get_fork_from_args(args) or DEFAULT_FORK
    result = fetcher.fetch_and_extract(
        repo,
        output_dir,
        extract_dir,
        release_tag=args.release,
        fork=actual_fork,
        dry_run=args.dry_run,
    )
    if result is not None:
        print_success()


def handle_fetch_with_fork(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: Any,
    output_dir: Path,
    extract_dir: Path,
    fork: ForkName,
) -> None:
    """Handle fetch operation for a single fork."""
    repo = FORKS[fork].repo
    logger.info(f"Using fork: {fork} ({repo})")

    fetcher_for_fork = get_fork_fetcher(fetcher, forgejo_fetcher, fork)
    result = fetcher_for_fork.fetch_and_extract(
        repo,
        output_dir,
        extract_dir,
        release_tag=args.release,
        fork=fork,
        dry_run=args.dry_run,
    )
    if result is not None:
        print_success()


def handle_multi_fork_update(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    output_dir: Path,
    extract_dir: Path,
    dry_run: bool,
) -> None:
    """Handle multi-fork update mode (-f without value)."""
    logger.info("Updating all forks with managed links...")
    fetcher.update_all_managed_forks(output_dir, extract_dir, dry_run=dry_run)
    forgejo_fetcher.update_all_managed_forks(output_dir, extract_dir, dry_run=dry_run)
    print("Done.")
