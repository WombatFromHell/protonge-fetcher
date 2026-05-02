"""CLI implementation for ProtonFetcher.

Thin re-export shim that delegates to extracted submodules.
"""

import logging
import sys
from pathlib import Path
from typing import Any

from ..common import ForkName
from ..exceptions import ProtonFetcherError
from ..forgejo_fetcher import ForgejoReleaseFetcher
from ..github_fetcher import GitHubReleaseFetcher

# Import from submodules (backward-compatible aliases)
from .argparse_builder import build_parser, parse_args
from .dispatch import (
    CLIContext,
    get_explicit_flags,
    get_operation_from_args,
    has_explicit_fork,
    is_flag_passed,
    resolve_default_operation,
)
from .dispatch import (
    dispatch as _dispatch,
)
from .fork_utils import (
    get_fork_fetcher,
    get_forks_to_list,
    print_links_for_fork,
    print_prunable_versions,
)
from .handlers import (
    handle_check_operation,
    handle_default_fetch,
    handle_fetch_with_fork,
    handle_list_operation,
    handle_ls_operation,
    handle_multi_fork_update,
    handle_prune_operation,
    handle_relink_operation,
    handle_rm_operation,
)
from .validators import (
    set_default_fork,
    validate_mutually_exclusive_args,
    validate_relink_requires_fork,
    was_flag_passed_explicitly,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Backward-compatible aliases (tests import these directly)
# ------------------------------------------------------------------

parse_arguments = parse_args


def _handle_ls_operation(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for handle_ls_operation."""
    handle_ls_operation(*args, **kwargs)


def _handle_list_operation(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for handle_list_operation."""
    handle_list_operation(*args, **kwargs)


def _handle_relink_operation(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for handle_relink_operation."""
    handle_relink_operation(*args, **kwargs)


def _handle_rm_operation(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for handle_rm_operation."""
    handle_rm_operation(*args, **kwargs)


def _handle_prune_operation(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for handle_prune_operation."""
    handle_prune_operation(*args, **kwargs)


def _handle_check_operation(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for handle_check_operation."""
    handle_check_operation(*args, **kwargs)


def _handle_default_fetch(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for handle_default_fetch."""
    handle_default_fetch(*args, **kwargs)


def _handle_fetch_with_fork(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for handle_fetch_with_fork."""
    handle_fetch_with_fork(*args, **kwargs)


def _handle_multi_fork_update(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for handle_multi_fork_update."""
    handle_multi_fork_update(*args, **kwargs)


def _get_fork_fetcher(*args: Any, **kwargs: Any) -> Any:
    """Backward-compatible alias for get_fork_fetcher."""
    return get_fork_fetcher(*args, **kwargs)


def _get_forks_to_list(*args: Any, **kwargs: Any) -> list[ForkName]:
    """Backward-compatible alias for get_forks_to_list."""
    return get_forks_to_list(*args, **kwargs)


def _print_prunable_versions(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for print_prunable_versions."""
    print_prunable_versions(*args, **kwargs)


def _print_links_for_fork(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for print_links_for_fork."""
    print_links_for_fork(*args, **kwargs)


def _is_flag_passed(*args: Any, **kwargs: Any) -> bool:
    """Backward-compatible alias for is_flag_passed."""
    return is_flag_passed(*args, **kwargs)


def _get_explicit_flags(*args: Any, **kwargs: Any) -> dict[str, bool]:
    """Backward-compatible alias for get_explicit_flags."""
    return get_explicit_flags(*args, **kwargs)


def _has_explicit_fork(*args: Any, **kwargs: Any) -> bool:
    """Backward-compatible alias for has_explicit_fork."""
    return has_explicit_fork(*args, **kwargs)


def _get_operation_from_args(*args: Any, **kwargs: Any) -> str | None:
    """Backward-compatible alias for get_operation_from_args."""
    return get_operation_from_args(*args, **kwargs)


def _resolve_default_operation(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for resolve_default_operation."""
    resolve_default_operation(*args, **kwargs)


def _set_default_fork(*args: Any, **kwargs: Any) -> Any:
    """Backward-compatible alias for set_default_fork."""
    return set_default_fork(*args, **kwargs)


def _was_flag_passed_explicitly(*args: Any, **kwargs: Any) -> bool:
    """Backward-compatible alias for was_flag_passed_explicitly."""
    return was_flag_passed_explicitly(*args, **kwargs)


def _validate_relink_requires_fork(*args: Any, **kwargs: Any) -> bool:
    """Backward-compatible alias for validate_relink_requires_fork."""
    return validate_relink_requires_fork(*args, **kwargs)


def _validate_check_vs_dry_run(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for validate_check_vs_dry_run."""
    validate_mutually_exclusive_args(*args, **kwargs)


def _validate_check_vs_list(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for validate_check_vs_list."""
    validate_mutually_exclusive_args(*args, **kwargs)


def _validate_prune_vs_check(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for validate_prune_vs_check."""
    validate_mutually_exclusive_args(*args, **kwargs)


def _validate_dry_run_conflicts(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for validate_dry_run_conflicts."""
    validate_mutually_exclusive_args(*args, **kwargs)


def _validate_mutually_exclusive_args(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible alias for validate_mutually_exclusive_args."""
    validate_mutually_exclusive_args(*args, **kwargs)


def setup_logging(debug: bool) -> None:
    """Set up logging based on debug flag."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(message)s")
    logging.getLogger().setLevel(log_level)
    if debug:
        logger.debug("Debug logging enabled")


def main() -> None:
    """CLI entry point."""
    argv_list = sys.argv[1:]
    explicit_flags = get_explicit_flags(argv_list)

    parser = build_parser()
    args = parse_args(parser)
    args = set_default_fork(args)
    validate_mutually_exclusive_args(args)

    extract_dir = Path(args.extract_dir).expanduser()
    output_dir = Path(args.output).expanduser()
    setup_logging(args.debug)

    try:
        fetcher = GitHubReleaseFetcher()
        forgejo_fetcher = ForgejoReleaseFetcher()

        ctx = CLIContext(
            fetcher=fetcher,
            forgejo_fetcher=forgejo_fetcher,
            args=args,
            extract_dir=extract_dir,
            output_dir=output_dir,
            explicit_flags=explicit_flags,
        )

        _dispatch(ctx, argv_list)

    except ProtonFetcherError as e:
        print(f"Error: {e}")
        raise SystemExit(1) from e
