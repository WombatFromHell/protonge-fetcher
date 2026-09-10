"""Version information for ProtonFetcher.

The embedded value is a sentinel; release builds stamp the real version into the
staging copy via Makefile / flake.nix so the source tree is never mutated.
"""

from importlib.metadata import PackageNotFoundError, version

__version__ = "DEV"


def _get_version() -> str:
    """Get version from embedded value or package metadata fallback."""
    if __version__ != "DEV":
        return __version__
    try:
        return version("protonge-fetcher")
    except PackageNotFoundError:
        return "unknown"
