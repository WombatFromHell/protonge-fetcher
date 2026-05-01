"""CLI implementation for ProtonFetcher."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Union

from .__version__ import __version__
from .common import DEFAULT_FORK, ForkName
from .exceptions import ProtonFetcherError
from .forgejo_fetcher import ForgejoReleaseFetcher
from .github_fetcher import GitHubReleaseFetcher

logger = logging.getLogger(__name__)


def _set_default_fork(args: argparse.Namespace) -> argparse.Namespace:
    """Set default fork if not provided (but not for --ls/--check/--prune)."""
    if not hasattr(args, "fork") and not args.ls and not args.check and not args.prune:
        args.fork = DEFAULT_FORK
    elif not hasattr(args, "fork") and (args.ls or args.check or args.prune):
        args.fork = None
    elif hasattr(args, "fork") and args.fork is None:
        pass  # Keep args.fork as None to signal multi-fork update
    return args


# Define mutually exclusive flag pairs as (flag_name, conflicting_flags)
_CONFLICT_RULES = [
    ("list", ["release"], "--list and --release cannot be used together"),
    ("ls", ["release", "list"], "--ls cannot be used with --release or --list"),
    (
        "rm",
        ["release", "list", "ls"],
        "--rm cannot be used with --release, --list, or --ls",
    ),
    (
        "relink",
        ["release", "list", "ls", "rm"],
        "--relink cannot be used with --release, --list, --ls, or --rm",
    ),
    (
        "check",
        ["list", "ls", "rm", "relink", "dry_run"],
        "--check cannot be used with --list, --ls, --rm, --relink, or --dry-run",
    ),
    (
        "prune",
        ["release", "list", "ls", "rm", "relink", "check"],
        "--prune cannot be used with --release, --list, --ls, --rm, --relink, or --check",
    ),
    (
        "dry_run",
        ["list", "ls", "rm", "relink", "check"],
        "--dry-run cannot be used with --list, --ls, --rm, --relink, or --check",
    ),
]


def _was_flag_passed_explicitly(flag_short: str, flag_long: str) -> bool:
    """Check if a flag was explicitly passed on the command line."""
    return any(
        arg in [flag_short, flag_long]
        or arg.startswith(f"{flag_long}=")
        or arg.startswith(f"{flag_short}=")
        for arg in sys.argv[1:]
    )


def _validate_relink_requires_fork(args: argparse.Namespace) -> bool:
    """Validate that --relink was used with explicit --fork flag."""
    if not args.relink:
        return True

    has_explicit_fork = _was_flag_passed_explicitly("-f", "--fork")
    if not has_explicit_fork:
        print(
            "Error: --relink requires --fork to specify which fork's links to recreate"
        )
        raise SystemExit(1)
    return True


def _validate_mutually_exclusive_args(args: argparse.Namespace) -> None:
    """Validate mutually exclusive arguments."""
    for flag_name, conflicting_flags, error_msg in _CONFLICT_RULES:
        if getattr(args, flag_name, False):
            conflicts = [cf for cf in conflicting_flags if getattr(args, cf, False)]
            if conflicts:
                print(f"Error: {error_msg}")
                raise SystemExit(1)

    _validate_relink_requires_fork(args)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=f"ProtonFetcher v{__version__} - Fetch and extract the latest ProtonGE release asset."
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"%(prog)s v{__version__}",
        help="show program's version number and exit",
    )
    parser.add_argument(
        "--extract-dir",
        "-x",
        default="~/.steam/steam/compatibilitytools.d/",
        help="Directory to extract the asset to (default: ~/.steam/steam/compatibilitytools.d/)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="~/Downloads/",
        help="Directory to download the asset to (default: ~/Downloads/)",
    )
    parser.add_argument(
        "--release",
        "-r",
        help="Manually specify a release tag (e.g., GE-Proton10-11) to download instead of the latest",
    )
    parser.add_argument(
        "--fork",
        "-f",
        default=argparse.SUPPRESS,
        nargs="?",
        const=None,
        choices=[
            fork.value
            for fork in [
                ForkName.GE_PROTON,
                ForkName.PROTON_EM,
                ForkName.CACHYOS,
                ForkName.DW_PROTON,
            ]
        ],
        help=f"ProtonGE fork to download (default: {DEFAULT_FORK.value}, available: {', '.join([fork.value for fork in [ForkName.GE_PROTON, ForkName.PROTON_EM, ForkName.CACHYOS, ForkName.DW_PROTON]])}). Use -f without a value to update all forks with managed links.",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List the 20 most recent release tags for the selected fork",
    )
    parser.add_argument(
        "--ls",
        action="store_true",
        help="List recognized symbolic links and their associated Proton fork folders",
    )
    parser.add_argument(
        "--rm",
        metavar="TAG",
        help="Remove a given Proton fork release folder and its associated link (if one exists)",
    )
    parser.add_argument(
        "--relink",
        action="store_true",
        help="Force recreation of symbolic links without downloading or extracting (use with --fork)",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Remove old unmanaged releases for all forks, keeping the N newest (use with --fork for specific fork)",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=3,
        metavar="N",
        help="Number of newest versions to keep when pruning (default: 3)",
    )
    parser.add_argument(
        "--check",
        "-c",
        action="store_true",
        help="Check if newer releases are available (use alone for all managed forks, or with --fork for specific fork)",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be downloaded/extracted/linked without making any changes",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()
    args = _set_default_fork(args)
    _validate_mutually_exclusive_args(args)
    return args


def setup_logging(debug: bool) -> None:
    """Set up logging based on debug flag."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(message)s")
    logging.getLogger().setLevel(log_level)
    if debug:
        logger.debug("Debug logging enabled")


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


def _get_forks_to_list(
    args: argparse.Namespace, list_all_forks: bool
) -> list[ForkName]:
    """Determine which forks to list based on arguments."""
    if list_all_forks or (not hasattr(args, "fork") or args.fork is None):
        return [
            ForkName.GE_PROTON,
            ForkName.PROTON_EM,
            ForkName.CACHYOS,
            ForkName.DW_PROTON,
        ]
    fork_enum = convert_fork_to_enum(args.fork)
    return [fork_enum]


def _print_links_for_fork(
    link_manager: Any, extract_dir: Path, fork: ForkName, show_versions: bool = False
) -> None:
    """Print links for a single fork."""
    links_info = link_manager.list_links(extract_dir, fork)
    print(f"Links for {fork.value}:")
    for link_name, target_path in links_info.items():
        if target_path:
            print(f"  {link_name} -> {target_path}")
        else:
            print(f"  {link_name} -> (not found)")

    if show_versions:
        installed = link_manager.get_installed_versions(extract_dir, fork)
        linked = link_manager.get_linked_versions(extract_dir, fork)
        prunable = [v for i, v in enumerate(installed, 1) if v not in linked and i > 3]
        if prunable:
            print(f"\nPrunable {fork.value} versions ({len(prunable)}):")
            for version in prunable:
                print(f"  ○ {version}")


# ------------------------------------------------------------------
# Operation handlers
# ------------------------------------------------------------------


def _handle_ls_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: argparse.Namespace,
    extract_dir: Path,
    list_all_forks: bool = False,
) -> None:
    """Handle the --ls operation to list symbolic links."""
    print("Listing recognized links and their associated Proton fork folders...")
    forks_to_check = _get_forks_to_list(args, list_all_forks)
    for fork in forks_to_check:
        lm = (
            forgejo_fetcher.link_manager
            if fork == ForkName.DW_PROTON
            else fetcher.link_manager
        )
        _print_links_for_fork(lm, extract_dir, fork, show_versions=True)
    print("Success")


def _handle_list_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: argparse.Namespace,
    extract_dir: Path,
) -> None:
    """Handle the --list operation flow."""
    if not hasattr(args, "fork") or args.fork is None:
        args.fork = DEFAULT_FORK

    target_fork: ForkName = convert_fork_to_enum(args.fork)
    from .common import FORKS

    repo = FORKS[target_fork].repo
    logger.info(f"Using fork: {target_fork} ({repo})")

    if target_fork == ForkName.DW_PROTON:
        tags = forgejo_fetcher.list_recent_releases(repo)
    else:
        tags = fetcher.list_recent_releases(repo)
    print("Recent releases:")
    for tag in tags:
        print(f"  {tag}")
    print("Success")


def _handle_relink_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: argparse.Namespace,
    extract_dir: Path,
) -> None:
    """Handle the --relink operation flow."""
    relink_fork = convert_fork_to_enum(
        args.fork if hasattr(args, "fork") and args.fork is not None else None
    )
    logger.info(f"Relinking {relink_fork} symlinks")
    if relink_fork == ForkName.DW_PROTON:
        forgejo_fetcher.relink_fork(extract_dir, relink_fork)
    else:
        fetcher.relink_fork(extract_dir, relink_fork)
    print("Success")


def _handle_rm_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: argparse.Namespace,
    extract_dir: Path,
) -> None:
    """Handle the --rm operation flow."""
    rm_fork = convert_fork_to_enum(
        args.fork if hasattr(args, "fork") and args.fork is not None else None
    )
    logger.info(f"Removing release: {args.rm}")
    if rm_fork == ForkName.DW_PROTON:
        forgejo_fetcher.link_manager.remove_release(extract_dir, args.rm, rm_fork)
    else:
        fetcher.link_manager.remove_release(extract_dir, args.rm, rm_fork)
    print("Success")


def _handle_prune_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: argparse.Namespace,
    extract_dir: Path,
) -> None:
    """Handle the --prune operation flow."""
    if hasattr(args, "fork") and args.fork is not None:
        forks_to_prune = [convert_fork_to_enum(args.fork)]
    else:
        forks_to_prune = [
            ForkName.GE_PROTON,
            ForkName.PROTON_EM,
            ForkName.CACHYOS,
            ForkName.DW_PROTON,
        ]

    all_to_prune: dict[ForkName, list[str]] = {}
    for fork in forks_to_prune:
        if fork == ForkName.DW_PROTON:
            kept, to_prune = forgejo_fetcher.prune_releases(
                extract_dir, fork, keep=args.keep, dry_run=True
            )
        else:
            kept, to_prune = fetcher.prune_releases(
                extract_dir, fork, keep=args.keep, dry_run=True
            )
        all_to_prune[fork] = to_prune

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

    print(
        "⚠️  WARNING: Pruning old releases may break Steam prefixes that depend on them."
    )
    print("Games using pruned versions will need to be reconfigured.")

    try:
        response = (
            input(f"\nProceed with pruning {total_to_prune} release(s)? [y/N]: ")
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        print("\nAborted")
        raise SystemExit(1) from None

    if response not in ("y", "yes"):
        print("Aborted")
        raise SystemExit(0)

    total_pruned = 0
    for fork in forks_to_prune:
        if all_to_prune[fork]:
            logger.info(f"Pruning old {fork.value} releases...")
            if fork == ForkName.DW_PROTON:
                kept, pruned = forgejo_fetcher.prune_releases(
                    extract_dir, fork, keep=args.keep, dry_run=False
                )
            else:
                kept, pruned = fetcher.prune_releases(
                    extract_dir, fork, keep=args.keep, dry_run=False
                )
            total_pruned += len(pruned)

    print(f"\nPruned {total_pruned} release(s)")
    print("Success")


def _handle_check_operation(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: argparse.Namespace,
    extract_dir: Path,
) -> None:
    """Handle the --check operation flow."""
    updates_available = False

    if not hasattr(args, "fork") or args.fork is None:
        forks_to_check = [
            ForkName.GE_PROTON,
            ForkName.PROTON_EM,
            ForkName.CACHYOS,
            ForkName.DW_PROTON,
        ]
        check_managed_only = True
    else:
        forks_to_check = [convert_fork_to_enum(args.fork)]
        check_managed_only = False

    for fork in forks_to_check:
        if check_managed_only:
            lm = (
                forgejo_fetcher.link_manager
                if fork == ForkName.DW_PROTON
                else fetcher.link_manager
            )
            if not lm.has_managed_links(extract_dir, fork):
                logger.debug(f"Skipping {fork}: no managed links found")
                continue

        try:
            if fork == ForkName.DW_PROTON:
                newer_release = forgejo_fetcher.check_for_updates(extract_dir, fork)
            else:
                newer_release = fetcher.check_for_updates(extract_dir, fork)
            if newer_release:
                print(f"New release available for {fork}: {newer_release}!")
                updates_available = True
            else:
                print(f"{fork}: up-to-date")
        except ProtonFetcherError as e:
            logger.error(f"Failed to check {fork}: {e}")

    if updates_available:
        raise SystemExit(0)
    raise SystemExit(1)


def _handle_default_fetch(
    fetcher: GitHubReleaseFetcher,
    repo: str,
    output_dir: Path,
    extract_dir: Path,
    args: argparse.Namespace,
) -> None:
    """Handle the default fetch and extract operation flow (GitHub forks only)."""
    actual_fork = convert_fork_to_enum(
        args.fork if hasattr(args, "fork") and args.fork is not None else None
    )
    result = fetcher.fetch_and_extract(
        repo,
        output_dir,
        extract_dir,
        release_tag=args.release,
        fork=actual_fork,
        dry_run=args.dry_run,
    )
    if result is not None:
        print("Success")


def _handle_fetch_with_fork(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: argparse.Namespace,
    output_dir: Path,
    extract_dir: Path,
    fork: ForkName,
) -> None:
    """Handle fetch operation for a single fork."""
    from .common import FORKS

    repo = FORKS[fork].repo
    logger.info(f"Using fork: {fork} ({repo})")

    if fork == ForkName.DW_PROTON:
        result = forgejo_fetcher.fetch_and_extract(
            repo,
            output_dir,
            extract_dir,
            release_tag=args.release,
            fork=fork,
            dry_run=args.dry_run,
        )
        if result is not None:
            print("Success")
    else:
        _handle_default_fetch(fetcher, repo, output_dir, extract_dir, args)


def _handle_multi_fork_update(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    output_dir: Path,
    extract_dir: Path,
    dry_run: bool,
) -> None:
    """Handle multi-fork update mode (-f without value)."""
    from .common import FORKS

    logger.info("Updating all forks with managed links...")
    results = fetcher.update_all_managed_forks(output_dir, extract_dir, dry_run=dry_run)

    if forgejo_fetcher.link_manager.has_managed_links(extract_dir, ForkName.DW_PROTON):
        logger.info("Updating DW-Proton: fetching latest release...")
        try:
            dw_repo = FORKS[ForkName.DW_PROTON].repo
            dw_result = forgejo_fetcher.fetch_and_extract(
                dw_repo,
                output_dir,
                extract_dir,
                fork=ForkName.DW_PROTON,
                dry_run=dry_run,
            )
            results[ForkName.DW_PROTON] = dw_result
            logger.debug("Successfully updated DW-Proton")
        except ProtonFetcherError as e:
            logger.error(f"Failed to update DW-Proton: {e}")
            results[ForkName.DW_PROTON] = None

    success_count = sum(1 for r in results.values() if r is not None)
    if success_count > 0:
        print(f"Successfully updated {success_count} fork(s)")
    else:
        print("No forks were updated")


# ------------------------------------------------------------------
# Dispatch
# ------------------------------------------------------------------


def _get_explicit_flags(argv_list: list[str]) -> dict[str, bool]:
    """Check which flags were explicitly passed on the command line."""
    return {
        "ls": "--ls" in argv_list,
        "list": "--list" in argv_list or "-l" in argv_list,
        "rm": "--rm" in argv_list or any(a.startswith("--rm=") for a in argv_list),
        "fork": "--fork" in argv_list
        or "-f" in argv_list
        or any(a.startswith("--fork=") or a.startswith("-f=") for a in argv_list),
        "release": "--release" in argv_list
        or "-r" in argv_list
        or any(a.startswith("--release=") or a.startswith("-r=") for a in argv_list),
    }


def _get_operation_from_args(args: argparse.Namespace) -> str | None:
    """Determine which operation was requested from parsed args."""
    if args.ls:
        return "ls"
    if args.list:
        return "list"
    if args.relink:
        return "relink"
    if args.rm:
        return "rm"
    if args.prune:
        return "prune"
    if args.check:
        return "check"
    return None


def _dispatch(
    fetcher: GitHubReleaseFetcher,
    forgejo_fetcher: ForgejoReleaseFetcher,
    args: argparse.Namespace,
    extract_dir: Path,
    output_dir: Path,
    explicit_flags: dict[str, bool],
) -> int:
    """Dispatch to the appropriate handler based on operation flags."""
    operation = _get_operation_from_args(args)

    handlers: dict[str, Any] = {
        "ls": lambda: _handle_ls_operation(
            fetcher,
            forgejo_fetcher,
            args,
            extract_dir,
            list_all_forks=not explicit_flags["fork"],
        ),
        "list": lambda: _handle_list_operation(
            fetcher, forgejo_fetcher, args, extract_dir
        ),
        "relink": lambda: _handle_relink_operation(
            fetcher, forgejo_fetcher, args, extract_dir
        ),
        "rm": lambda: _handle_rm_operation(fetcher, forgejo_fetcher, args, extract_dir),
        "prune": lambda: _handle_prune_operation(
            fetcher, forgejo_fetcher, args, extract_dir
        ),
        "check": lambda: _handle_check_operation(
            fetcher, forgejo_fetcher, args, extract_dir
        ),
    }

    if operation in handlers:
        handlers[operation]()
        return 0

    # No explicit operation: default to fetch or ls based on functional flags
    if explicit_flags["fork"] or explicit_flags["release"]:
        if hasattr(args, "fork") and args.fork is None:
            _handle_multi_fork_update(
                fetcher, forgejo_fetcher, output_dir, extract_dir, args.dry_run
            )
        else:
            fork = convert_fork_to_enum(
                args.fork if hasattr(args, "fork") and args.fork is not None else None
            )
            _handle_fetch_with_fork(
                fetcher, forgejo_fetcher, args, output_dir, extract_dir, fork
            )
    else:
        _handle_ls_operation(
            fetcher, forgejo_fetcher, args, extract_dir, list_all_forks=True
        )

    return 0


def main() -> None:
    """CLI entry point."""
    argv_list = sys.argv[1:]
    explicit_flags = _get_explicit_flags(argv_list)

    args = parse_arguments()
    extract_dir = Path(args.extract_dir).expanduser()
    output_dir = Path(args.output).expanduser()
    setup_logging(args.debug)

    try:
        fetcher = GitHubReleaseFetcher()
        forgejo_fetcher = ForgejoReleaseFetcher()

        _dispatch(
            fetcher, forgejo_fetcher, args, extract_dir, output_dir, explicit_flags
        )

    except ProtonFetcherError as e:
        print(f"Error: {e}")
        raise SystemExit(1) from e
