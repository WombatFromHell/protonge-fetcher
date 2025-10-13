#!/usr/bin/env python3
"""
fetcher.py

Fetch and extract the latest ProtonGE GitHub release asset
"""

from __future__ import annotations

import argparse
import logging
import re
import tarfile
import tempfile
from pathlib import Path
from typing import NoReturn

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
GITHUB_URL_PATTERN = r"/releases/tag/([^/?#]+)"
PROTONGE_ASSET_PATTERN = r"GE-Proton\d+[\w.-]*\.tar\.gz"


class FetchError(Exception):
    """Raised when fetching or extracting a release fails."""


class GitHubReleaseFetcher:
    """Handles fetching and extracting GitHub release assets."""

    def __init__(
        self, timeout: int = DEFAULT_TIMEOUT, session: requests.Session | None = None
    ) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch_latest_tag(self, repo: str) -> str:
        """Get the latest release tag by following the redirect from /releases/latest.

        Args:
            repo: Repository in format 'owner/repo'

        Returns:
            The latest release tag

        Raises:
            FetchError: If unable to determine the tag from the redirect
        """
        url = f"https://github.com/{repo}/releases/latest"
        try:
            response = self.session.head(
                url, allow_redirects=True, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.RequestException as e:
            self._raise(f"Failed to fetch latest tag for {repo}: {e}")

        match = re.search(GITHUB_URL_PATTERN, response.url)
        if not match:
            self._raise(f"Could not determine latest tag from URL: {response.url}")

        return match.group(1)

    def find_asset_by_pattern(self, repo: str, tag: str, pattern: str) -> str:
        """Find an asset matching the given pattern in a GitHub release.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            pattern: Regex pattern to match asset names

        Returns:
            The asset name matching the pattern

        Raises:
            FetchError: If no matching asset is found
        """
        url = f"https://github.com/{repo}/releases/tag/{tag}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            self._raise(f"Failed to fetch release page for {repo}/{tag}: {e}")

        matches = re.findall(pattern, response.text)
        if not matches:
            self._raise(f"No asset matching pattern '{pattern}' found in {repo}/{tag}")

        return matches[0]

    def download_asset(
        self, repo: str, tag: str, asset_name: str, out_path: Path
    ) -> Path:
        """Download a specific asset from a GitHub release.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename to download
            out_path: Path where the asset will be saved

        Returns:
            Path to the downloaded file

        Raises:
            FetchError: If download fails or asset not found
        """
        url = f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"

        try:
            with self.session.get(url, stream=True, timeout=self.timeout) as response:
                if response.status_code == 404:
                    self._raise(f"Asset not found: {asset_name}")
                response.raise_for_status()

                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
        except requests.RequestException as e:
            self._raise(f"Failed to download {asset_name}: {e}")

        return out_path

    def extract_archive(self, archive_path: Path, target_dir: Path) -> None:
        """Extract tar.gz archive to the target directory.

        Args:
            archive_path: Path to the tar.gz archive
            target_dir: Directory to extract into

        Raises:
            FetchError: If extraction fails
        """
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(archive_path) as tar:
                tar.extractall(path=target_dir, filter=tarfile.data_filter)
            logger.info(f"Extracted {archive_path} to {target_dir}")
        except (tarfile.TarError, EOFError) as e:
            self._raise(f"Failed to extract archive {archive_path}: {e}")

    def fetch_and_extract(self, repo: str, asset_name: str, target_dir: Path) -> Path:
        """Fetch the latest release asset and extract it to the target directory.

        Args:
            repo: Repository in format 'owner/repo'
            asset_name: Asset filename to download, or regex pattern to find it
            target_dir: Directory to extract into

        Returns:
            Path to the target directory
        """
        tag = self.fetch_latest_tag(repo)
        logger.info(f"Fetching {asset_name} from {repo} tag {tag}")

        # If asset_name looks like a pattern (contains regex chars), find the actual name
        # Check for regex metacharacters: [] () + ? | ^ $ \ but not . (common in filenames)
        if any(c in asset_name for c in r"[]()^$\+?|"):
            asset_name = self.find_asset_by_pattern(repo, tag, asset_name)
            logger.info(f"Found asset: {asset_name}")

        with tempfile.TemporaryDirectory(prefix="ghrel-") as temp_dir:
            temp_path = Path(temp_dir) / asset_name
            self.download_asset(repo, tag, asset_name, temp_path)
            self.extract_archive(temp_path, target_dir)

        return target_dir

    @staticmethod
    def _raise(message: str) -> NoReturn:
        """Log error and raise FetchError."""
        logger.error(message)
        raise FetchError(message)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch and extract the latest ProtonGE release asset."
    )
    # The 'repo' argument has been removed as it is now hardcoded.
    parser.add_argument(
        "--asset-name",
        default=PROTONGE_ASSET_PATTERN,
        help=f"Asset filename to download, or regex pattern to match asset name (default: '{PROTONGE_ASSET_PATTERN}')",
    )
    parser.add_argument(
        "--target-dir",
        default=".",
        help="Directory to extract the asset to (default: current directory)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    # The repository is now hardcoded.
    repo = "GloriousEggroll/proton-ge-custom"

    try:
        fetcher = GitHubReleaseFetcher()
        fetcher.fetch_and_extract(repo, args.asset_name, Path(args.target_dir))
        print("Success")
    except FetchError as e:
        print(f"Error: {e}")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
