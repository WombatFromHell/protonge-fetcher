"""Version information for ProtonFetcher."""

from importlib.metadata import PackageNotFoundError, version

# This value is replaced at build time by the Makefile
__version__ = "DEV"


def _get_version() -> str:
    """Get version from embedded value or package metadata fallback."""
    if __version__ != "DEV":
        return __version__
    try:
        return version("protonge-fetcher")
    except PackageNotFoundError:
        return "unknown"


__version__ = _get_version()
