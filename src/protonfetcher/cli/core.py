"""CLI implementation for ProtonFetcher."""

import logging
import sys
from pathlib import Path

from ..exceptions import ProtonFetcherError
from ..forgejo_fetcher import ForgejoReleaseFetcher
from ..github_fetcher import GitHubReleaseFetcher
from .argparse_builder import build_parser, parse_args
from .dispatch import (
    CLIContext,
    get_explicit_flags,
)
from .dispatch import (
    dispatch as _dispatch,
)
from .validators import (
    set_default_fork,
    validate_mutually_exclusive_args,
)

logger = logging.getLogger(__name__)


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
