"""CLI implementation for ProtonFetcher."""

import fcntl
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..dirs import lock_path
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


@contextmanager
def _instance_lock() -> Iterator[None]:
    """Hold an exclusive flock for the whole run so two instances cannot race.

    Concurrent runs share the same *.partial files, extraction directory and
    compatibilitytools.d symlinks, so the second one is refused rather than waited on.
    """
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # An O_RDWR fd starts at EOF, so the holder PID has to be read from the path.
            holder = path.read_text().strip() or "another process"
            raise ProtonFetcherError(
                f"another protonfetcher (PID {holder}) is running"
            ) from None
        # shortcut: if this file is unlinked while held (tmpfiles ageing /tmp), a later
        # instance locks a fresh file. Upgrade to re-open-and-relock if that ever bites.
        os.write(fd, f"{os.getpid()}\n".encode())
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


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
        verify_checksum = not args.skip_checksum
        fetcher = GitHubReleaseFetcher(verify_checksum=verify_checksum)
        forgejo_fetcher = ForgejoReleaseFetcher(verify_checksum=verify_checksum)

        ctx = CLIContext(
            fetcher=fetcher,
            forgejo_fetcher=forgejo_fetcher,
            args=args,
            extract_dir=extract_dir,
            output_dir=output_dir,
            explicit_flags=explicit_flags,
        )

        with _instance_lock():
            _dispatch(ctx, argv_list)

    except KeyboardInterrupt:
        # Ctrl+C is a user decision, not a fault: no traceback, and SIGINT's code.
        # 1 is already 'updates available' for --check, so this gets 130.
        print("\nInterrupted. Partial downloads are kept — run again to resume.")
        raise SystemExit(130) from None

    except (ProtonFetcherError, OSError) as e:
        print(f"Error: {e}")
        raise SystemExit(1) from e
