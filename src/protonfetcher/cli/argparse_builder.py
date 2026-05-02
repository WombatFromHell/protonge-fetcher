"""Argument parser construction for the CLI.

Extracted from cli.py to separate parser construction from dispatch logic.
"""

import argparse

from protonfetcher.__version__ import __version__
from protonfetcher.common import DEFAULT_FORK, FORKS


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser with all defined arguments."""
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
        "--fork",
        "-f",
        default=argparse.SUPPRESS,
        nargs="?",
        const=None,
        choices=[fork.value for fork in FORKS],
        help=f"ProtonGE fork to download (default: {DEFAULT_FORK.value}, available: {', '.join(fork.value for fork in FORKS)}). Use -f without a value to update all forks with managed links.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=None,
        metavar="N",
        help="Number of newest versions to keep when pruning (default: prune all)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    # Mutually exclusive operation group
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List the 20 most recent release tags for the selected fork",
    )
    group.add_argument(
        "--ls",
        action="store_true",
        help="List recognized symbolic links and their associated Proton fork folders",
    )
    group.add_argument(
        "--relink",
        action="store_true",
        help="Force recreation of symbolic links without downloading or extracting (use with --fork)",
    )
    group.add_argument(
        "--prune",
        action="store_true",
        help="Remove old releases for all forks, keeping the N newest (use with --fork for specific fork)",
    )

    # --release is not mutually exclusive; can be used with --rm
    parser.add_argument(
        "--release",
        "-r",
        help="Manually specify a release tag (e.g., GE-Proton10-11) to download instead of the latest",
    )

    # --rm is not mutually exclusive; can be used with --fork or --release
    parser.add_argument(
        "--rm",
        action="store_true",
        help="Remove a release directory and its symlinks. Use with --fork to remove all symlinks for that fork, or with --release to remove a specific tag.",
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

    return parser


def parse_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """Parse arguments using the given parser."""
    return parser.parse_args()
