"""Dispatch logic for the CLI.

Extracted from cli.py to isolate routing logic.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from protonfetcher.forgejo_fetcher import ForgejoReleaseFetcher
from protonfetcher.github_fetcher import GitHubReleaseFetcher

from .fork_utils import (
    convert_fork_to_enum,
    get_fork_from_args,
    is_flag_passed,
)
from .handlers import (
    handle_check_operation,
    handle_fetch_with_fork,
    handle_list_operation,
    handle_ls_operation,
    handle_multi_fork_update,
    handle_prune_operation,
    handle_relink_operation,
    handle_rm_operation,
)


@dataclass(frozen=True)
class CLIContext:
    """Bundles all parameters needed for CLI dispatch.

    Reduces the parameter count in dispatch functions from 7 to 1.
    """

    fetcher: GitHubReleaseFetcher
    forgejo_fetcher: ForgejoReleaseFetcher
    args: Any
    extract_dir: Path
    output_dir: Path
    explicit_flags: dict[str, bool]


logger = logging.getLogger(__name__)


def get_explicit_flags(argv_list: list[str]) -> dict[str, bool]:
    """Check which flags were explicitly passed on the command line."""
    return {
        "ls": "--ls" in argv_list,
        "list": is_flag_passed(argv_list, "--list", "-l"),
        "rm": "--rm" in argv_list,
        "fork": is_flag_passed(argv_list, "--fork", "-f"),
        "release": is_flag_passed(argv_list, "--release", "-r"),
        "dry_run": "--dry-run" in argv_list,
    }


def has_explicit_fork(argv_list: list[str]) -> bool:
    """Check if --fork was explicitly passed on the command line."""
    return is_flag_passed(argv_list, "--fork", "-f")


def get_operation_from_args(args: Any) -> str | None:
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


def _default_operation(ctx: CLIContext, argv_list: list[str]) -> str:
    """Default to an implicit update when a fork/release was given, else 'ls'."""
    if has_explicit_fork(argv_list) or ctx.explicit_flags["release"]:
        return "update"
    return "ls"


def _handle_update(ctx: CLIContext) -> None:
    """Run the implicit update: all forks, or the one named by --fork."""
    if hasattr(ctx.args, "fork") and ctx.args.fork is None:
        handle_multi_fork_update(
            ctx.fetcher,
            ctx.forgejo_fetcher,
            ctx.output_dir,
            ctx.extract_dir,
            ctx.args.dry_run,
        )
        return
    fork = get_fork_from_args(ctx.args) or convert_fork_to_enum(None)
    handle_fetch_with_fork(
        ctx.fetcher,
        ctx.forgejo_fetcher,
        ctx.args,
        ctx.output_dir,
        ctx.extract_dir,
        fork,
    )


def dispatch(ctx: CLIContext, argv_list: list[str]) -> int:
    """Dispatch to the appropriate handler based on operation flags."""
    operation = get_operation_from_args(ctx.args) or _default_operation(ctx, argv_list)

    handlers: dict[str, Callable[[], None]] = {
        "ls": lambda: handle_ls_operation(
            ctx.fetcher,
            ctx.forgejo_fetcher,
            ctx.args,
            ctx.extract_dir,
            list_all_forks=not has_explicit_fork(argv_list),
        ),
        "list": lambda: handle_list_operation(
            ctx.fetcher, ctx.forgejo_fetcher, ctx.args, ctx.extract_dir
        ),
        "relink": lambda: handle_relink_operation(
            ctx.fetcher, ctx.forgejo_fetcher, ctx.args, ctx.extract_dir
        ),
        "rm": lambda: handle_rm_operation(
            ctx.fetcher, ctx.forgejo_fetcher, ctx.args, ctx.extract_dir
        ),
        "prune": lambda: handle_prune_operation(
            ctx.fetcher, ctx.forgejo_fetcher, ctx.args, ctx.extract_dir
        ),
        "check": lambda: handle_check_operation(
            ctx.fetcher, ctx.forgejo_fetcher, ctx.args, ctx.extract_dir
        ),
        "update": lambda: _handle_update(ctx),
    }

    handlers[operation]()
    return 0
