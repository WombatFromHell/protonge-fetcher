"""Dispatch logic for the CLI.

Extracted from cli.py to isolate routing logic.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from protonfetcher.forgejo_fetcher import ForgejoReleaseFetcher
from protonfetcher.github_fetcher import GitHubReleaseFetcher

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


def is_flag_passed(argv_list: list[str], long_flag: str, short_flag: str) -> bool:
    """Check if a flag was explicitly passed (standalone or with value)."""
    return any(
        arg == long_flag
        or arg == short_flag
        or arg.startswith(f"{long_flag}=")
        or arg.startswith(f"{short_flag}=")
        for arg in argv_list
    )


def get_explicit_flags(argv_list: list[str]) -> dict[str, bool]:
    """Check which flags were explicitly passed on the command line."""
    return {
        "ls": "--ls" in argv_list,
        "list": is_flag_passed(argv_list, "--list", "-l"),
        "rm": is_flag_passed(argv_list, "--rm", "-r"),
        "fork": is_flag_passed(argv_list, "--fork", "-f"),
        "release": is_flag_passed(argv_list, "--release", "-r"),
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


def dispatch(ctx: CLIContext, argv_list: list[str]) -> int:
    """Dispatch to the appropriate handler based on operation flags."""
    operation = get_operation_from_args(ctx.args)

    handlers: dict[str, Any] = {
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
    }

    if operation in handlers:
        handlers[operation]()
        return 0

    # No explicit operation: resolve default
    resolve_default_operation(ctx, argv_list)
    return 0


def resolve_default_operation(ctx: CLIContext, argv_list: list[str]) -> None:
    """Resolve the default operation when no explicit flag is given."""
    from .fork_utils import convert_fork_to_enum, get_fork_from_args

    if has_explicit_fork(argv_list) or ctx.explicit_flags["release"]:
        if hasattr(ctx.args, "fork") and ctx.args.fork is None:
            handle_multi_fork_update(
                ctx.fetcher,
                ctx.forgejo_fetcher,
                ctx.output_dir,
                ctx.extract_dir,
                ctx.args.dry_run,
            )
        else:
            fork = get_fork_from_args(ctx.args) or convert_fork_to_enum(None)
            handle_fetch_with_fork(
                ctx.fetcher,
                ctx.forgejo_fetcher,
                ctx.args,
                ctx.output_dir,
                ctx.extract_dir,
                fork,
            )
    else:
        handle_ls_operation(
            ctx.fetcher,
            ctx.forgejo_fetcher,
            ctx.args,
            ctx.extract_dir,
            list_all_forks=True,
        )
