"""CLI implementation for ProtonFetcher."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Union

from .common import DEFAULT_FORK, ForkName
from .exceptions import ProtonFetcherError
from .github_fetcher import GitHubReleaseFetcher

logger = logging.getLogger(__name__)


def _set_default_fork(args: argparse.Namespace) -> argparse.Namespace:
    """Set default fork if not provided (but not for --ls which should handle all forks)."""
    if not hasattr(args, "fork") and not args.ls:
        args.fork = DEFAULT_FORK
    elif not hasattr(args, "fork") and args.ls:
        args.fork = None  # Will be handled specially for --ls
    return args


def _validate_mutually_exclusive_args(args: argparse.Namespace) -> None:
    """Validate mutually exclusive arguments."""
    # --list and --release can't be used together
    # --ls and --rm can't be used together with other conflicting flags
    if args.list and args.release:
        print("Error: --list and --release cannot be used together")
        raise SystemExit(1)
    if args.ls and (args.release or args.list):
        print("Error: --ls cannot be used with --release or --list")
        raise SystemExit(1)
    if args.rm and (args.release or args.list or args.ls):
        print("Error: --rm cannot be used with --release, --list, or --ls")
        raise SystemExit(1)
    # Check if --relink was used without explicit --fork (before _set_default_fork)
    relink_without_fork = args.relink and not any(
        arg in ["--fork", "-f"] or arg.startswith("--fork=") or arg.startswith("-f=")
        for arg in sys.argv[1:]
    )
    if relink_without_fork:
        print(
            "Error: --relink requires --fork to specify which fork's links to recreate"
        )
        raise SystemExit(1)
    if args.relink and (args.release or args.list or args.ls or args.rm):
        print("Error: --relink cannot be used with --release, --list, --ls, or --rm")
        raise SystemExit(1)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch and extract the latest ProtonGE release asset."
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
        default=argparse.SUPPRESS,  # Don't set a default, check for attribute existence
        choices=[fork.value for fork in [ForkName.GE_PROTON, ForkName.PROTON_EM]],
        help=f"ProtonGE fork to download (default: {DEFAULT_FORK.value}, available: {', '.join([fork.value for fork in [ForkName.GE_PROTON, ForkName.PROTON_EM]])})",
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

    # Configure logging but ensure it works with pytest caplog
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
    )

    # For pytest compatibility, also ensure the root logger has the right level
    logging.getLogger().setLevel(log_level)

    # Log if debug mode is enabled
    if debug:
        # Check if we're in a test environment (pytest would have certain characteristics)
        # If running test, log to make sure it's captured by caplog
        logger.debug("Debug logging enabled")


def convert_fork_to_enum(fork_arg: Union[str, ForkName, None]) -> ForkName:
    """Convert fork argument to ForkName enum."""
    if isinstance(fork_arg, str):
        # Convert string to ForkName enum
        try:
            return ForkName(fork_arg)
        except ValueError:
            print(f"Error: Invalid fork '{fork_arg}'")
            raise SystemExit(1) from None
    elif fork_arg is None:
        return DEFAULT_FORK
    else:
        # It's already a ForkName enum
        return fork_arg


def handle_ls_operation(
    fetcher: GitHubReleaseFetcher,
    args: argparse.Namespace,
    extract_dir: Path,
    list_all_forks: bool = False,
) -> None:
    """Handle the --ls operation to list symbolic links."""
    print("Listing recognized links and their associated Proton fork folders...")

    # If list_all_forks is True, or if no fork specified, list links for all forks
    if list_all_forks or (not hasattr(args, "fork") or args.fork is None):
        forks_to_check = [ForkName.GE_PROTON, ForkName.PROTON_EM]
    else:
        # Validate and narrow the type - convert string to ForkName if needed
        fork_enum = convert_fork_to_enum(args.fork)
        forks_to_check = [fork_enum]

    for fork in forks_to_check:
        # fork is now properly typed as ForkName
        links_info = fetcher.link_manager.list_links(extract_dir, fork)
        print(f"Links for {fork}:")
        for link_name, target_path in links_info.items():
            if target_path:
                print(f"  {link_name} -> {target_path}")
            else:
                print(f"  {link_name} -> (not found)")


def _handle_ls_operation_flow(
    fetcher: GitHubReleaseFetcher,
    args: argparse.Namespace,
    extract_dir: Path,
    list_all_forks: bool = False,
) -> None:
    """Handle the --ls operation flow."""
    handle_ls_operation(fetcher, args, extract_dir, list_all_forks)
    print("Success")


def _handle_list_operation_flow(fetcher: GitHubReleaseFetcher, repo: str) -> None:
    """Handle the --list operation flow."""
    logger.info("Fetching recent releases...")
    tags = fetcher.release_manager.list_recent_releases(repo)
    print("Recent releases:")
    for tag in tags:
        print(f"  {tag}")
    print("Success")  # Print success to maintain consistency


def _handle_relink_operation_flow(
    fetcher: GitHubReleaseFetcher, args: argparse.Namespace, extract_dir: Path
) -> None:
    """Handle the --relink operation flow."""
    # Use the provided fork
    relink_fork = convert_fork_to_enum(
        args.fork if hasattr(args, "fork") and args.fork is not None else None
    )
    logger.info(f"Relinking {relink_fork} symlinks")
    fetcher.relink_fork(extract_dir, relink_fork)
    print("Success")


def _handle_rm_operation_flow(
    fetcher: GitHubReleaseFetcher, args: argparse.Namespace, extract_dir: Path
) -> None:
    """Handle the --rm operation flow."""
    # Use the provided fork or default to DEFAULT_FORK
    rm_fork = convert_fork_to_enum(
        args.fork if hasattr(args, "fork") and args.fork is not None else None
    )
    logger.info(f"Removing release: {args.rm}")
    fetcher.link_manager.remove_release(extract_dir, args.rm, rm_fork)
    print("Success")


def _handle_default_operation_flow(
    fetcher: GitHubReleaseFetcher,
    repo: str,
    output_dir: Path,
    extract_dir: Path,
    args: argparse.Namespace,
) -> None:
    """Handle the default fetch and extract operation flow."""
    # For operations that continue after --ls/--list/--rm, ensure fork is set
    actual_fork = convert_fork_to_enum(
        args.fork if hasattr(args, "fork") and args.fork is not None else None
    )

    fetcher.fetch_and_extract(
        repo,
        output_dir,
        extract_dir,
        release_tag=args.release,
        fork=actual_fork,
    )
    print("Success")


def main() -> None:
    """CLI entry point."""
    import sys

    # Check for explicit flags in sys.argv before full parsing to determine default behavior
    argv_list = sys.argv[1:]

    # Check if operation flags were explicitly provided in sys.argv
    has_explicit_ls = any(arg in ["--ls"] for arg in argv_list)
    has_explicit_list = any(arg in ["--list", "-l"] for arg in argv_list)
    has_explicit_rm = any(arg in ["--rm"] for arg in argv_list) or any(
        arg.startswith("--rm=") for arg in argv_list
    )

    # Check if functional flags were explicitly provided in sys.argv
    has_explicit_fork = any(arg in ["--fork", "-f"] for arg in argv_list) or any(
        arg.startswith("--fork=") or arg.startswith("-f=") for arg in argv_list
    )
    has_explicit_release = any(arg in ["--release", "-r"] for arg in argv_list) or any(
        arg.startswith("--release=") or arg.startswith("-r=") for arg in argv_list
    )

    # Parse the arguments
    args = parse_arguments()

    # Expand user home directory (~) in paths
    extract_dir = Path(args.extract_dir).expanduser()
    output_dir = Path(args.output).expanduser()

    # Set up logging
    setup_logging(args.debug)

    try:
        fetcher = GitHubReleaseFetcher()

        # Check if any explicit operation flag is provided
        has_operation_flag = has_explicit_ls or has_explicit_list or has_explicit_rm

        # Check if functional flags were provided originally (before _set_default_fork)
        has_functional_flags = has_explicit_fork or has_explicit_release

        # Handle --ls flag (explicitly set)
        if args.ls:
            # For explicit --ls flag, list all forks if no specific fork was provided in the command
            _handle_ls_operation_flow(
                fetcher, args, extract_dir, list_all_forks=not has_explicit_fork
            )
            return

        # Handle --list flag
        if args.list:
            # Set default fork if not provided
            if not hasattr(args, "fork") or args.fork is None:
                args.fork = DEFAULT_FORK

            # Get the repo based on selected fork - handle string-to-enum conversion
            target_fork: ForkName = convert_fork_to_enum(args.fork)
            from .common import FORKS

            repo = FORKS[target_fork].repo
            logger.info(f"Using fork: {target_fork} ({repo})")

            _handle_list_operation_flow(fetcher, repo)
            return

        # Handle --relink flag
        if args.relink:
            _handle_relink_operation_flow(fetcher, args, extract_dir)
            return

        # Handle --rm flag
        if args.rm:
            _handle_rm_operation_flow(fetcher, args, extract_dir)
            return

        # If no explicit operation flags (not --ls, --list, --rm), default to either ls or fetch based on presence of functional flags
        if not has_operation_flag:
            # If functional flags were provided (--fork or --release), proceed with fetch operation
            if has_functional_flags:
                # Use the fork specified by the user or default if not specified
                actual_fork = convert_fork_to_enum(
                    args.fork
                    if hasattr(args, "fork") and args.fork is not None
                    else None
                )
                from .common import FORKS

                repo = FORKS[actual_fork].repo
                logger.info(f"Using fork: {actual_fork} ({repo})")

                _handle_default_operation_flow(
                    fetcher, repo, output_dir, extract_dir, args
                )
                return
            else:
                # No operation flags and no functional flags - default to listing all links
                _handle_ls_operation_flow(
                    fetcher, args, extract_dir, list_all_forks=True
                )
                return

        # Handle default operation (fetch and extract) - fallback, though shouldn't reach here due to operation flag logic
        # This fallback is here to make sure we handle any remaining cases
        actual_fork = convert_fork_to_enum(
            args.fork if hasattr(args, "fork") and args.fork is not None else None
        )
        from .common import FORKS

        repo = FORKS[actual_fork].repo
        logger.info(f"Using fork: {actual_fork} ({repo})")

        _handle_default_operation_flow(fetcher, repo, output_dir, extract_dir, args)

    except ProtonFetcherError as e:
        print(f"Error: {e}")
        raise SystemExit(1) from e
