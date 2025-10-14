#!/usr/bin/env python3
"""
fetcher.py

Fetch and extract the latest ProtonGE GitHub release asset
"""

from __future__ import annotations

import argparse
import logging
import re
import time
import tarfile
import subprocess
from pathlib import Path
from typing import NoReturn

from typing import Iterator, Optional


class Spinner:
    """A simple native spinner progress indicator without external dependencies."""

    def __init__(
        self,
        iterable: Iterator | None = None,
        total: Optional[int] = None,
        desc: str = "",
        unit: str = "it",
        unit_scale: bool = False,
        disable: bool = False,
        **kwargs,
    ):
        self._iterable = iterable
        self.total = total
        self.desc = desc
        self.unit = unit
        self.unit_scale = unit_scale
        self.disable = disable
        self.current = 0
        self.spinner_chars = "|/-\\"
        self.spinner_idx = 0
        self.start_time = time.time()

    def __enter__(self):
        if not self.disable and self.desc:
            print(f"{self.desc}: ", end="", flush=True)
        return self

    def __exit__(self, *args):
        if not self.disable:
            print()  # New line at the end

    def update(self, n: int = 1) -> None:
        if self.disable:
            return

        self.current += n
        if self.total:
            # Show progress bar with percentage
            percent = self.current / self.total * 100
            bar_size = 20
            filled_size = (
                int(bar_size * self.current // self.total) if self.total > 0 else 0
            )
            bar = "=" * filled_size + " " * (bar_size - filled_size)
            elapsed = time.time() - self.start_time
            rate = self.current / elapsed if elapsed > 0 else 0

            # Format rate based on unit_scale
            if self.unit_scale and self.unit == "B":
                rate_str = (
                    f"{rate:.2f}B/s"
                    if rate < 1024
                    else f"{rate / 1024:.2f}KB/s"
                    if rate < 1024**2
                    else f"{rate / 1024**2:.2f}MB/s"
                )
            else:
                rate_str = f"{rate:.1f}{self.unit}/s"

            print(
                f"\r{self.desc}: [{bar}] {percent:.1f}% ({rate_str})",
                end="",
                flush=True,
            )
        else:
            # Just show spinner
            spinner_char = self.spinner_chars[self.spinner_idx % 4]
            print(f"\r{self.desc}: {spinner_char}", end="", flush=True)
            self.spinner_idx += 1

    def close(self) -> None:
        if not self.disable:
            print()  # New line when closing

    def __iter__(self) -> Iterator:
        if self._iterable is not None:
            yield from self._iterable
        else:
            # When no iterable provided, yield nothing or a range if total is specified
            if self.total:
                for i in range(self.total):
                    yield i
                    self.update(1)


logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
GITHUB_URL_PATTERN = r"/releases/tag/([^/?#]+)"
PROTONGE_ASSET_PATTERN = r"GE-Proton\d+[\w.-]*\.tar\.gz"


class FetchError(Exception):
    """Raised when fetching or extracting a release fails."""


class GitHubReleaseFetcher:
    """Handles fetching and extracting GitHub release assets."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def _curl_get(
        self, url: str, headers: Optional[dict] = None, stream: bool = False
    ) -> subprocess.CompletedProcess:
        """Make a GET request using curl.

        Args:
            url: URL to make request to
            headers: Optional headers to include
            stream: Whether to stream the response

        Returns:
            CompletedProcess result from subprocess
        """
        cmd = [
            "curl",
            "-L",  # Follow redirects
            "-s",  # Silent mode
            "-S",  # Show errors
            "-f",  # Fail on HTTP error
            "--max-time",
            str(self.timeout),
        ]

        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        if stream:
            # For streaming, we'll handle differently
            pass

        cmd.append(url)

        return subprocess.run(cmd, capture_output=True, text=True)

    def _curl_head(
        self, url: str, headers: Optional[dict] = None
    ) -> subprocess.CompletedProcess:
        """Make a HEAD request using curl.

        Args:
            url: URL to make request to
            headers: Optional headers to include

        Returns:
            CompletedProcess result from subprocess
        """
        cmd = [
            "curl",
            "-I",  # Header only
            "-s",  # Silent mode
            "-S",  # Show errors
            "-f",  # Fail on HTTP error
            "--max-time",
            str(self.timeout),
        ]

        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        cmd.append(url)

        return subprocess.run(cmd, capture_output=True, text=True)

    def _curl_download(
        self, url: str, output_path: Path, headers: Optional[dict] = None
    ) -> subprocess.CompletedProcess:
        """Download a file using curl.

        Args:
            url: URL to download from
            output_path: Path to save the file
            headers: Optional headers to include

        Returns:
            CompletedProcess result from subprocess
        """
        cmd = [
            "curl",
            "-L",  # Follow redirects
            "-s",  # Silent mode (will show progress)
            "-S",  # Show errors
            "-f",  # Fail on HTTP error
            "--max-time",
            str(self.timeout),
            "-o",
            str(output_path),  # Output file
            "--progress-bar",  # Show progress bar
        ]

        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        cmd.append(url)

        return subprocess.run(cmd, capture_output=True, text=True)

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
            response = self._curl_head(url)
            if response.returncode != 0:
                self._raise(f"Failed to fetch latest tag for {repo}: {response.stderr}")
        except Exception as e:
            self._raise(f"Failed to fetch latest tag for {repo}: {e}")

        # Parse the redirect URL from curl response headers
        location_match = re.search(
            r"Location: [^\r\n]*?(/releases/tag/[^/?#\r\n]+)",
            response.stdout,
            re.IGNORECASE,
        )
        if not location_match:
            # Try another pattern for the redirect
            location_match = re.search(r"URL=(.*)", response.stdout)
            if location_match:
                redirected_url = location_match.group(1).strip()
            else:
                # If no Location header found, use the original URL
                redirected_url = url
        else:
            redirected_url = location_match.group(1)

        match = re.search(GITHUB_URL_PATTERN, redirected_url)
        if not match:
            self._raise(f"Could not determine latest tag from URL: {redirected_url}")

        tag = match.group(1)
        logger.info(f"Found latest tag: {tag}")
        return tag

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
        logger.info(f"Fetching release page: {url}")

        try:
            response = self._curl_get(url)
            if response.returncode != 0:
                self._raise(
                    f"Failed to fetch release page for {repo}/{tag}: {response.stderr}"
                )
        except Exception as e:
            self._raise(f"Failed to fetch release page for {repo}/{tag}: {e}")

        # Try multiple approaches to find the asset
        asset_name = None

        # Approach 1: Look for direct download links
        download_pattern = rf'href="/{repo}/releases/download/{tag}/([^"]+{pattern})"'
        matches = re.findall(download_pattern, response.stdout)
        if matches:
            asset_name = matches[0]
            logger.info(f"Found asset using download pattern: {asset_name}")
            return asset_name

        # Approach 2: Look for the pattern in any href
        href_pattern = rf'href="[^"]*({pattern})"'
        matches = re.findall(href_pattern, response.stdout)
        if matches:
            asset_name = matches[0]
            logger.info(f"Found asset using href pattern: {asset_name}")
            return asset_name

        # Approach 3: Look for the pattern in the entire page
        matches = re.findall(pattern, response.stdout)
        if matches:
            asset_name = matches[0]
            logger.info(f"Found asset using direct pattern: {asset_name}")
            return asset_name

        # Approach 4: Try to construct the asset name from the tag
        # This is a fallback for when the pattern doesn't match
        constructed_name = f"{tag}.tar.gz"
        if re.search(pattern.replace(r"\.", r"."), constructed_name):
            logger.info(f"Using constructed asset name: {constructed_name}")
            return constructed_name

        # Log a snippet of the HTML for debugging
        html_snippet = (
            response.stdout[:500] + "..."
            if len(response.stdout) > 500
            else response.stdout
        )
        logger.debug(f"HTML snippet: {html_snippet}")

        self._raise(f"No asset matching pattern '{pattern}' found in {repo}/{tag}")

    def download_asset(
        self, repo: str, tag: str, asset_name: str, out_path: Path
    ) -> Path:
        """Download a specific asset from a GitHub release with progress bar.

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
        logger.info(f"Downloading asset from: {url}")

        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            result = self._curl_download(url, out_path)
            if result.returncode != 0:
                if "404" in result.stderr or "not found" in result.stderr.lower():
                    self._raise(f"Asset not found: {asset_name}")
                self._raise(f"Failed to download {asset_name}: {result.stderr}")
        except Exception as e:
            self._raise(f"Failed to download {asset_name}: {e}")

        logger.info(f"Downloaded asset to: {out_path}")
        return out_path

    def extract_archive(self, archive_path: Path, target_dir: Path) -> None:
        """Extract tar.gz archive to the target directory with progress bar.

        Args:
            archive_path: Path to the tar.gz archive
            target_dir: Directory to extract into

        Raises:
            FetchError: If extraction fails
        """
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(archive_path) as tar:
                members = tar.getmembers()
                # Wrap the list of members directly with spinner
                spinner = Spinner(
                    iterable=iter(members),  # Convert list to iterator
                    desc=f"Extracting {archive_path.name}",
                    unit="file",
                    disable=False,  # Always show spinner since we implemented it natively
                    total=len(members),
                )
                for member in spinner:
                    tar.extract(member, path=target_dir, filter=tarfile.data_filter)

            logger.info(f"Extracted {archive_path} to {target_dir}")
        except (tarfile.TarError, EOFError) as e:
            self._raise(f"Failed to extract archive {archive_path}: {e}")

    def _ensure_directory_is_writable(self, path: Path) -> None:
        """Check if a directory is accessible and writable.

        Args:
            path: Directory path to check

        Raises:
            FetchError: If directory is not accessible or not writable
        """
        # Create the directory if it doesn't exist
        path.mkdir(parents=True, exist_ok=True)

        # Check if path is a directory
        if not path.is_dir():
            self._raise(f"Path exists but is not a directory: {path}")

        # Check if directory is writable
        try:
            # Try to create a temporary file to check write permissions
            import tempfile

            with tempfile.TemporaryFile(dir=path) as _:
                pass  # Just test that we can create a file
        except OSError:
            self._raise(f"Directory is not writable: {path}")

    def _ensure_curl_available(self) -> None:
        """Check if curl is available in the environment.

        Raises:
            FetchError: If curl is not found in PATH
        """
        import shutil

        if shutil.which("curl") is None:
            self._raise("curl is not available in PATH. Please install curl.")

    def fetch_and_extract(
        self, repo: str, asset_name: str, output_dir: Path, extract_dir: Path
    ) -> Path:
        """Fetch the latest release asset and extract it to the target directory.

        Args:
            repo: Repository in format 'owner/repo'
            asset_name: Asset filename to download, or regex pattern to find it
            output_dir: Directory to download the asset to
            extract_dir: Directory to extract the asset to

        Returns:
            Path to the extracted directory
        """
        # Early validation checks
        self._ensure_curl_available()
        self._ensure_directory_is_writable(output_dir)
        self._ensure_directory_is_writable(extract_dir)

        tag = self.fetch_latest_tag(repo)
        logger.info(f"Fetching {asset_name} from {repo} tag {tag}")

        # If asset_name looks like a pattern (contains regex chars), find the actual name
        # Check for regex metacharacters: [] () + ? | ^ $ \ but not . (common in filenames)
        if any(c in asset_name for c in r"[]()^$\+?|"):
            asset_name = self.find_asset_by_pattern(repo, tag, asset_name)
            logger.info(f"Found asset: {asset_name}")

        # Download to the output directory
        output_path = output_dir / asset_name
        self.download_asset(repo, tag, asset_name, output_path)

        # Extract to the extract directory
        self.extract_archive(output_path, extract_dir)

        return extract_dir

    @staticmethod
    def _raise(message: str) -> NoReturn:
        """Raise FetchError without logging."""
        raise FetchError(message)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch and extract the latest ProtonGE release asset."
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
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Expand user home directory (~) in paths
    extract_dir = Path(args.extract_dir).expanduser()
    output_dir = Path(args.output).expanduser()

    # Set up logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )

    # Native spinner implementation is always available
    pass

    # target `github.com/GloriousEggroll/proton-ge-custom/releases/latest`
    repo = "GloriousEggroll/proton-ge-custom"
    asset_name = PROTONGE_ASSET_PATTERN

    try:
        fetcher = GitHubReleaseFetcher()
        fetcher.fetch_and_extract(repo, asset_name, output_dir, extract_dir)
        print("Success")
    except FetchError as e:
        print(f"Error: {e}")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
