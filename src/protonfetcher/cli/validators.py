"""Validation functions for CLI argument parsing.

Extracted from cli.py to centralize validation logic.
"""

import argparse
import sys

from protonfetcher.common import DEFAULT_FORK


def was_flag_passed_explicitly(flag_short: str, flag_long: str) -> bool:
    """Check if a flag was explicitly passed on the command line."""
    return any(
        arg in [flag_short, flag_long]
        or arg.startswith(f"{flag_long}=")
        or arg.startswith(f"{flag_short}=")
        for arg in sys.argv[1:]
    )


def validate_relink_requires_fork(args: argparse.Namespace) -> bool:
    """Validate that --relink was used with explicit --fork flag."""
    if not args.relink:
        return True

    has_explicit_fork = was_flag_passed_explicitly("-f", "--fork")
    if not has_explicit_fork:
        print(
            "Error: --relink requires --fork to specify which fork's links to recreate"
        )
        raise SystemExit(1)
    return True


def validate_check_vs_dry_run(args: argparse.Namespace) -> None:
    """Validate --check vs --dry-run mutual exclusion."""
    if args.check and args.dry_run:
        print("Error: --check and --dry-run cannot be used together")
        raise SystemExit(1)


def validate_check_vs_list(args: argparse.Namespace) -> None:
    """Validate --check vs --list/--ls mutual exclusion."""
    if args.check and (args.list or args.ls):
        print("Error: --check cannot be used with --list or --ls")
        raise SystemExit(1)


def validate_prune_vs_check(args: argparse.Namespace) -> None:
    """Validate --prune vs --check mutual exclusion."""
    if args.prune and args.check:
        print("Error: --prune and --check cannot be used together")
        raise SystemExit(1)


def validate_dry_run_conflicts(args: argparse.Namespace) -> None:
    """Validate --dry-run conflicts with read-only operations."""
    if args.dry_run and (args.list or args.ls or args.rm or args.relink):
        print("Error: --dry-run cannot be used with --list, --ls, --rm, or --relink")
        raise SystemExit(1)


def validate_mutually_exclusive_args(args: argparse.Namespace) -> None:
    """Validate mutually exclusive arguments."""
    validate_check_vs_dry_run(args)
    validate_check_vs_list(args)
    validate_prune_vs_check(args)
    validate_dry_run_conflicts(args)
    validate_relink_requires_fork(args)


def set_default_fork(args: argparse.Namespace) -> argparse.Namespace:
    """Set default fork if not provided (but not for --ls/--check/--prune)."""
    has_fork_attr = hasattr(args, "fork")
    is_read_only_op = args.ls or args.check or args.prune

    if not has_fork_attr:
        if is_read_only_op:
            args.fork = None
        else:
            args.fork = DEFAULT_FORK
    # If fork attr exists (set by argparse), keep it as-is
    #   - None signals multi-fork update
    #   - value is the explicit fork choice
    return args
